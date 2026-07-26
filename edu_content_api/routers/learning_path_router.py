import ast
import json
import math
import operator
import os
import shutil
import uuid
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from psycopg import Connection
from psycopg.rows import dict_row

from ai_plan_service import (
    generate_ai_plan, generate_fallback_plan,
    generate_mcq_options, generate_mcq_batch,
    generate_mcq_batch_no_ai,
)
from auth import _has_active_premium, get_current_user
from bootstrap import UPLOAD_DIR
from database import get_db_conn
from models import UserDB

router = APIRouter()

DIAGNOSTIC_PER_SUBIECT = 5   # 5 ex per subiect → 15 total
MIN_EASE = 1.3
ALLOWED_SOLUTION_TYPES = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


# ─── SM-2 ─────────────────────────────────────────────────────────────────────

def _sm2(interval: int, reps: int, ease: float, quality: int):
    if quality >= 3:
        new_interval = 1 if reps == 0 else (6 if reps == 1 else round(interval * ease))
        new_ease = max(MIN_EASE, ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        new_reps = reps + 1
    else:
        new_interval = 1
        new_ease = max(MIN_EASE, ease - 0.2)
        new_reps = 0
    return new_interval, new_reps, new_ease


# ─── Answer checking ──────────────────────────────────────────────────────────

_ARITH_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod,
}
_ARITH_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_arith_eval(node):
    """Evaluează SIGUR o expresie aritmetică, fără eval — doar numere și + - * / ( ) **.
    Ridică ValueError la orice nod nepermis. Previne code injection și DoS."""
    if isinstance(node, ast.Expression):
        return _safe_arith_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ARITH_BINOPS:
        left = _safe_arith_eval(node.left)
        right = _safe_arith_eval(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > 100 or abs(left) > 1e6):
            raise ValueError("exponent prea mare")  # anti-DoS (ex: 9**9**9)
        return _ARITH_BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ARITH_UNARY:
        return _ARITH_UNARY[type(node.op)](_safe_arith_eval(node.operand))
    raise ValueError("expresie nepermisă")


def _eval_numeric(expr: str) -> Optional[float]:
    import re
    if not expr:
        return None
    s = re.sub(r'\$', '', expr.strip())
    s = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'((\1)/(\2))', s)
    s = re.sub(r'\\sqrt\{([^}]+)\}', r'(\1)**0.5', s)
    s = re.sub(r'\\[a-zA-Z]+', '', s)
    s = re.sub(r'[{}]', '', s).strip()
    if not s:
        return None
    if not re.match(r'^[\d\s\+\-\*\/\.\(\)]+$', s):
        return None
    try:
        result = _safe_arith_eval(ast.parse(s, mode="eval"))
        if isinstance(result, (int, float)) and math.isfinite(result):
            return float(result)
    except Exception:
        pass
    return None


def _check_answer(user_answer: str, answer_latex: Optional[str], answer_numeric: Optional[float]) -> bool:
    target = answer_numeric
    if target is None and answer_latex:
        target = _eval_numeric(answer_latex)
    if target is None:
        return False
    user_val = _eval_numeric(user_answer or "")
    if user_val is None:
        return False
    return abs(user_val - target) < 1e-4


# ─── Diagnostic — Start ───────────────────────────────────────────────────────

@router.post("/diagnostic/start", tags=["Learning Path"])
def start_diagnostic(
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """
    Pornește un test diagnostic de tip grilă (free).
    Selectează exerciții cu answer_numeric_value pentru a genera MCQ.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        # Anulează teste active anterioare
        cur.execute(
            "UPDATE diagnostic_tests SET status='abandoned' WHERE user_id=%s AND status='active'",
            (str(current_user.id),),
        )

        selected = []
        for subiect_key in ["1", "2", "3"]:
            cur.execute(
                """
                SELECT e.id, e.statement_latex, e.statement_text,
                       e.answer_latex, e.answer_numeric_value, e.difficulty,
                       e.solution_latex, e.scoring_guide_latex,
                       e.metadata,
                       (SELECT t.key FROM exercise_tags et2
                        JOIN tags t ON t.id = et2.tag_id AND t.namespace = 'topic'
                        WHERE et2.exercise_id = e.id LIMIT 1) AS topic_key,
                       (SELECT t.label FROM exercise_tags et2
                        JOIN tags t ON t.id = et2.tag_id AND t.namespace = 'topic'
                        WHERE et2.exercise_id = e.id LIMIT 1) AS topic_label
                FROM exercises e
                WHERE e.status = 'READY'
                  AND (e.metadata::jsonb->>'diagnostic_grila')::boolean = true
                  AND EXISTS (
                      SELECT 1 FROM exercise_tags et3
                      JOIN tags t3 ON t3.id = et3.tag_id
                      WHERE et3.exercise_id = e.id
                        AND t3.namespace = 'subiect'
                        AND t3.key = %s
                  )
                ORDER BY RANDOM()
                LIMIT %s
                """,
                (subiect_key, DIAGNOSTIC_PER_SUBIECT),
            )
            selected.extend(cur.fetchall())

        if len(selected) < 3:
            raise HTTPException(
                status_code=503,
                detail="Nu există suficiente exerciții READY pentru testul diagnostic.",
            )

        # Creează testul
        cur.execute(
            "INSERT INTO diagnostic_tests (user_id, status, total_exercises) VALUES (%s,'active',%s) RETURNING id",
            (str(current_user.id), len(selected)),
        )
        test_id = str(cur.fetchone()["id"])

        # Construim harta subiect_num per exercițiu
        ex_meta_map: dict = {}
        for i, ex in enumerate(selected):
            meta = ex.get("metadata") or {}
            if isinstance(meta, str):
                meta = json.loads(meta)
            ex_meta_map[str(ex["id"])] = meta.get("subiect")

        # --- Generare MCQ ---
        batch_input = [
            {
                "id": str(ex["id"]),
                "statement_latex": ex.get("statement_latex") or "",
                "solution_latex": ex.get("solution_latex") or "",
                "scoring_guide_latex": ex.get("scoring_guide_latex") or "",
                "answer_latex": ex.get("answer_latex") or "",
                "answer_numeric_value": ex.get("answer_numeric_value"),
            }
            for ex in selected
        ]

        # Inserăm exercițiile cu opțiunile MCQ
        exercises_out = []
        for i, ex in enumerate(selected):
            ex_id = str(ex["id"])
            subiect_num = ex_meta_map.get(ex_id)

            # Opțiunile pre-definite din metadata au prioritate maximă
            meta = ex.get("metadata") or {}
            if isinstance(meta, str):
                meta = json.loads(meta)

            predefined_opts = meta.get("mcq_options")
            predefined_cidx = meta.get("correct_option_index")

            if predefined_opts and predefined_cidx is not None:
                options = predefined_opts
                correct_idx = predefined_cidx
            else:
                # Fallback: generare automată din soluție
                single = generate_mcq_batch_no_ai([{
                    "id": ex_id,
                    "solution_latex": ex.get("solution_latex") or "",
                    "scoring_guide_latex": ex.get("scoring_guide_latex") or "",
                    "answer_latex": ex.get("answer_latex") or "",
                    "answer_numeric_value": ex.get("answer_numeric_value"),
                }])
                if single:
                    options = single[0]["options"]
                    correct_idx = single[0]["correct_index"]
                else:
                    options = None
                    correct_idx = None

            cur.execute(
                """
                INSERT INTO diagnostic_exercises
                  (test_id, exercise_id, sort_order, subiect_num, topic_key, topic_label,
                   options, correct_option_index)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (test_id, exercise_id) DO NOTHING
                """,
                (
                    test_id, ex_id, i, subiect_num,
                    ex.get("topic_key"), ex.get("topic_label"),
                    json.dumps(options) if options else None,
                    correct_idx,
                ),
            )

            exercises_out.append({
                "id": ex_id,
                "statement_latex": ex["statement_latex"],
                "statement_text": ex.get("statement_text"),
                "difficulty": ex.get("difficulty"),
                "topic_key": ex.get("topic_key"),
                "topic_label": ex.get("topic_label"),
                "options": options,
            })

        conn.commit()
        return {"test_id": test_id, "exercises": exercises_out, "total": len(selected)}


# ─── Diagnostic — Get current ─────────────────────────────────────────────────

@router.get("/diagnostic/history", tags=["Learning Path"])
def get_diagnostic_history(
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """Returnează toate încercările de diagnostic ale utilizatorului, ordonate descendent."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, status, total_exercises, correct_count, score_pct,
                   weak_topics, solution_file_path, created_at, completed_at
            FROM diagnostic_tests
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (str(current_user.id),),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/diagnostic/current", tags=["Learning Path"])
def get_current_diagnostic(
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM diagnostic_tests WHERE user_id=%s ORDER BY created_at DESC LIMIT 1",
            (str(current_user.id),),
        )
        test = cur.fetchone()
        if not test:
            return {"test": None}
        cur.execute(
            """
            SELECT de.*, e.statement_latex, e.statement_text,
                   e.answer_latex, e.answer_numeric_value, e.difficulty
            FROM diagnostic_exercises de
            JOIN exercises e ON e.id = de.exercise_id
            WHERE de.test_id = %s
            ORDER BY de.sort_order
            """,
            (str(test["id"]),),
        )
        return {"test": dict(test), "exercises": [dict(r) for r in cur.fetchall()]}


# ─── Diagnostic — Submit ──────────────────────────────────────────────────────

@router.post("/diagnostic/{test_id}/submit", tags=["Learning Path"])
def submit_diagnostic(
    test_id: str,
    body: dict,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """
    Trimite răspunsurile la testul diagnostic (free).
    body: {answers: [{exercise_id, selected_option?: int, answer?: str}]}
    """
    answers: list = body.get("answers", [])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM diagnostic_tests WHERE id=%s AND user_id=%s AND status='active'",
            (test_id, str(current_user.id)),
        )
        test = cur.fetchone()
        if not test:
            raise HTTPException(status_code=404, detail="Test negăsit sau deja completat.")

        cur.execute(
            """
            SELECT de.exercise_id, de.topic_key, de.topic_label, de.subiect_num,
                   de.correct_option_index,
                   e.answer_latex, e.answer_numeric_value
            FROM diagnostic_exercises de
            JOIN exercises e ON e.id = de.exercise_id
            WHERE de.test_id = %s
            """,
            (test_id,),
        )
        ex_map = {str(r["exercise_id"]): r for r in cur.fetchall()}

        correct_count = 0
        topic_stats: dict = {}

        for ans in answers:
            ex_id = str(ans.get("exercise_id", ""))
            if ex_id not in ex_map:
                continue

            ex = ex_map[ex_id]

            # MCQ sau open
            selected_opt = ans.get("selected_option")  # int sau None
            user_text = str(ans.get("answer", "")).strip()

            if selected_opt is not None and ex.get("correct_option_index") is not None:
                correct = int(selected_opt) == int(ex["correct_option_index"])
                stored_answer = str(selected_opt)
            else:
                correct = _check_answer(user_text, ex.get("answer_latex"), ex.get("answer_numeric_value"))
                stored_answer = user_text

            if correct:
                correct_count += 1

            tk = ex.get("topic_key") or "unknown"
            if tk not in topic_stats:
                topic_stats[tk] = {
                    "topic_label": ex.get("topic_label") or tk,
                    "subiect": ex.get("subiect_num"),
                    "seen": 0,
                    "correct": 0,
                }
            topic_stats[tk]["seen"] += 1
            if correct:
                topic_stats[tk]["correct"] += 1

            cur.execute(
                """
                UPDATE diagnostic_exercises
                SET user_answer=%s, selected_option=%s, is_correct=%s, answered_at=NOW()
                WHERE test_id=%s AND exercise_id=%s
                """,
                (stored_answer, selected_opt, correct, test_id, ex_id),
            )

        total = len(ex_map)
        score_pct = round(correct_count / total * 100) if total else 0

        weak_topics = [
            {
                "topic_key": tk,
                "topic_label": stats["topic_label"],
                "subiect": stats["subiect"],
                "score_pct": round(stats["correct"] / stats["seen"] * 100) if stats["seen"] else 0,
                "seen": stats["seen"],
                "correct": stats["correct"],
            }
            for tk, stats in topic_stats.items()
        ]

        cur.execute(
            """
            UPDATE diagnostic_tests
            SET status='completed', correct_count=%s, score_pct=%s,
                weak_topics=%s, completed_at=NOW()
            WHERE id=%s
            """,
            (correct_count, score_pct, json.dumps(weak_topics), test_id),
        )
        conn.commit()

        return {
            "test_id": test_id,
            "score_pct": score_pct,
            "correct_count": correct_count,
            "total": total,
            "weak_topics": weak_topics,
        }


# ─── Diagnostic — Upload solution ─────────────────────────────────────────────

@router.post("/diagnostic/{test_id}/upload-solution", tags=["Learning Path"])
async def upload_solution(
    test_id: str,
    file: UploadFile = File(...),
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """Încarcă soluția scrisă (PDF/imagine) la finalul testului diagnostic."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id FROM diagnostic_tests WHERE id=%s AND user_id=%s AND status='completed'",
            (test_id, str(current_user.id)),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Test negăsit sau incomplet.")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_SOLUTION_TYPES:
        raise HTTPException(status_code=422, detail=f"Tip fișier nepermis. Acceptăm: {', '.join(ALLOWED_SOLUTION_TYPES)}")

    filename = f"diagnostic_solution_{test_id}_{uuid.uuid4().hex[:8]}{ext}"
    dest = os.path.join(UPLOAD_DIR, filename)

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE diagnostic_tests SET solution_file_path=%s WHERE id=%s",
            (filename, test_id),
        )
        conn.commit()

    return {"filename": filename, "url": f"/uploads/{filename}"}


# ─── Learning Path — Generate ─────────────────────────────────────────────────

@router.post("/learning-path/generate", tags=["Learning Path"])
def generate_learning_path(
    body: dict,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    """
    Generează planul de studiu personalizat din rezultatele diagnosticului.
    Apelează Claude (dacă ANTHROPIC_API_KEY e setat) pentru un plan real.
    """
    diag_id = body.get("diagnostic_test_id")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM diagnostic_tests WHERE id=%s AND user_id=%s AND status='completed'",
            (diag_id, str(current_user.id)),
        )
        diag = cur.fetchone()
        if not diag:
            raise HTTPException(status_code=404, detail="Testul diagnostic nu a fost completat.")

        diag_dict = {
            "score_pct": diag["score_pct"],
            "correct_count": diag["correct_count"],
            "total": diag["total_exercises"],
            "weak_topics": diag["weak_topics"] or [],
        }

        # Generează planul AI (Claude) sau fallback
        ai_plan = generate_ai_plan(diag_dict)
        if ai_plan is None:
            ai_plan = generate_fallback_plan(diag_dict)
            ai_plan["_source"] = "fallback"
        else:
            ai_plan["_source"] = "claude"

        weak_map = {t["topic_key"]: t for t in (diag["weak_topics"] or [])}

        # Topicuri disponibile în DB
        cur.execute(
            """
            SELECT t.key AS topic_key, t.label AS topic_label,
                   ts.key AS subiect_key,
                   COUNT(DISTINCT e.id) AS exercise_count
            FROM tags t
            JOIN exercise_tags et  ON et.tag_id  = t.id
            JOIN exercises e       ON e.id        = et.exercise_id
            JOIN exercise_tags ets ON ets.exercise_id = e.id
            JOIN tags ts           ON ts.id = ets.tag_id AND ts.namespace = 'subiect'
            WHERE t.namespace = 'topic'
              AND e.status = 'READY'
              AND (
                  e.metadata::jsonb->>'is_container' IS NULL
                  OR (e.metadata::jsonb->>'is_container')::boolean = false
              )
              AND e.metadata::jsonb->>'parent_external_id' IS NULL
            GROUP BY t.key, t.label, ts.key
            HAVING COUNT(DISTINCT e.id) >= 3
            ORDER BY ts.key::integer, COUNT(DISTINCT e.id) DESC
            """,
        )
        available = cur.fetchall()

        # Șterge planul existent
        cur.execute("DELETE FROM learning_paths WHERE user_id=%s", (str(current_user.id),))

        cur.execute(
            """
            INSERT INTO learning_paths
              (user_id, diagnostic_test_id, status, total_nodes, ai_plan)
            VALUES (%s,%s,'active',%s,%s) RETURNING id
            """,
            (str(current_user.id), diag_id, len(available), json.dumps(ai_plan)),
        )
        path_id = str(cur.fetchone()["id"])

        # Noduri ordonate după prioritate
        nodes = []
        for topic in available:
            tk = topic["topic_key"]
            try:
                subiect_num = int(topic["subiect_key"])
            except (TypeError, ValueError):
                subiect_num = 1

            if tk in weak_map:
                dscore = weak_map[tk]["score_pct"]
                priority = 1 if dscore < 30 else (2 if dscore < 60 else 4)
            else:
                dscore = None
                priority = 3

            target = min(topic["exercise_count"], max(5, round(topic["exercise_count"] * 0.4)))
            nodes.append({
                "topic_key": tk, "topic_label": topic["topic_label"],
                "subiect_num": subiect_num, "priority": priority,
                "target": target, "diag_score": dscore,
            })

        nodes.sort(key=lambda n: (n["subiect_num"], n["priority"]))

        for order, node in enumerate(nodes):
            cur.execute(
                """
                INSERT INTO learning_path_nodes
                  (path_id, topic_key, topic_label, subiect_num, priority,
                   target_exercises, diagnostic_score_pct, sort_order)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    path_id, node["topic_key"], node["topic_label"],
                    node["subiect_num"], node["priority"],
                    node["target"], node["diag_score"], order,
                ),
            )

        conn.commit()
        return {
            "path_id": path_id,
            "total_nodes": len(nodes),
            "ai_plan_source": ai_plan.get("_source", "fallback"),
        }


# ─── Learning Path — Get ──────────────────────────────────────────────────────

@router.get("/learning-path/", tags=["Learning Path"])
def get_learning_path(
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    is_premium = _has_active_premium(str(current_user.id), conn)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM learning_paths WHERE user_id=%s", (str(current_user.id),))
        path = cur.fetchone()
        if not path:
            return {"path": None, "nodes": [], "is_premium": is_premium}

        cur.execute(
            "SELECT * FROM learning_path_nodes WHERE path_id=%s ORDER BY sort_order",
            (str(path["id"]),),
        )
        all_nodes = cur.fetchall()
        preview_only = not is_premium
        nodes = all_nodes[:3] if preview_only else all_nodes

        path_dict = dict(path)
        # ai_plan e vizibil și pentru free (e parte din diagnostic care e free)
        return {
            "path": path_dict,
            "nodes": [dict(n) for n in nodes],
            "total_nodes": len(all_nodes),
            "preview_only": preview_only,
            "is_premium": is_premium,
            "ai_plan": path_dict.get("ai_plan"),
        }


# ─── Learning Path — Today ────────────────────────────────────────────────────

@router.get("/learning-path/today", tags=["Learning Path"])
def get_today_recommendations(
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if not _has_active_premium(str(current_user.id), conn):
        raise HTTPException(status_code=403, detail="Recomandările zilnice necesită abonament Premium.")

    today = date.today()
    recommendations = []

    with conn.cursor(row_factory=dict_row) as cur:
        # Spaced repetition scadent
        cur.execute(
            """
            SELECT sri.exercise_id AS sr_exercise_id, sri.next_review_date, sri.ease_factor,
                   e.id, e.statement_latex, e.statement_text,
                   e.answer_latex, e.answer_numeric_value, e.difficulty
            FROM spaced_repetition_items sri
            JOIN exercises e ON e.id = sri.exercise_id
            WHERE sri.user_id = %s AND sri.next_review_date <= %s
            ORDER BY sri.next_review_date, sri.ease_factor
            LIMIT 5
            """,
            (str(current_user.id), today),
        )
        for row in cur.fetchall():
            d = dict(row)
            d["source"] = "spaced_repetition"
            recommendations.append(d)

        sr_count = len(recommendations)

        cur.execute("SELECT id FROM learning_paths WHERE user_id=%s", (str(current_user.id),))
        path_row = cur.fetchone()

        if path_row:
            cur.execute(
                """
                SELECT * FROM learning_path_nodes
                WHERE path_id=%s AND status != 'mastered'
                ORDER BY sort_order LIMIT 3
                """,
                (str(path_row["id"]),),
            )
            for node in cur.fetchall():
                cur.execute(
                    """
                    SELECT e.id, e.statement_latex, e.statement_text,
                           e.answer_latex, e.answer_numeric_value, e.difficulty
                    FROM exercises e
                    JOIN exercise_tags et ON et.exercise_id = e.id
                    JOIN tags t ON t.id = et.tag_id
                    WHERE t.namespace = 'topic' AND t.key = %s
                      AND e.status = 'READY'
                      AND (
                          e.metadata::jsonb->>'is_container' IS NULL
                          OR (e.metadata::jsonb->>'is_container')::boolean = false
                      )
                      AND e.metadata::jsonb->>'parent_external_id' IS NULL
                      AND e.id NOT IN (
                          SELECT exercise_id FROM student_progress
                          WHERE student_id = %s AND completed = true
                      )
                    ORDER BY RANDOM() LIMIT 2
                    """,
                    (node["topic_key"], str(current_user.id)),
                )
                for ex in cur.fetchall():
                    d = dict(ex)
                    d["source"] = "learning_path"
                    d["topic_key"] = node["topic_key"]
                    d["topic_label"] = node["topic_label"]
                    d["node_id"] = str(node["id"])
                    recommendations.append(d)

    return {
        "date": str(today),
        "recommendations": recommendations,
        "sr_count": sr_count,
        "new_count": len(recommendations) - sr_count,
    }


# ─── Node progress ────────────────────────────────────────────────────────────

@router.post("/learning-path/node/{node_id}/progress", tags=["Learning Path"])
def update_node_progress(
    node_id: str,
    body: dict,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if not _has_active_premium(str(current_user.id), conn):
        raise HTTPException(status_code=403, detail="Necesită abonament Premium.")

    exercise_id = body.get("exercise_id")
    is_correct: bool = bool(body.get("is_correct", False))

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT lpn.* FROM learning_path_nodes lpn
            JOIN learning_paths lp ON lp.id = lpn.path_id
            WHERE lpn.id = %s AND lp.user_id = %s
            """,
            (node_id, str(current_user.id)),
        )
        node = cur.fetchone()
        if not node:
            raise HTTPException(status_code=404, detail="Nod negăsit.")

        new_seen = node["exercises_seen"] + 1
        new_correct = node["exercises_correct"] + (1 if is_correct else 0)
        new_score = round(new_correct / new_seen * 100) if new_seen else 0
        threshold = max(3, round(node["target_exercises"] * 0.6))
        new_status = (
            "mastered" if new_score >= 80 and new_seen >= threshold
            else "in_progress" if new_seen > 0
            else node["status"]
        )

        cur.execute(
            """
            UPDATE learning_path_nodes
            SET exercises_seen=%s, exercises_correct=%s, score_pct=%s, status=%s
            WHERE id=%s
            """,
            (new_seen, new_correct, new_score, new_status, node_id),
        )

        if exercise_id:
            if not is_correct:
                cur.execute(
                    """
                    INSERT INTO spaced_repetition_items
                      (user_id, exercise_id, interval_days, repetitions, ease_factor, next_review_date)
                    VALUES (%s,%s,1,0,2.5,CURRENT_DATE+1)
                    ON CONFLICT (user_id, exercise_id) DO UPDATE
                    SET interval_days=1, repetitions=0,
                        ease_factor=GREATEST(1.3, spaced_repetition_items.ease_factor-0.2),
                        next_review_date=CURRENT_DATE+1, last_reviewed_at=NOW()
                    """,
                    (str(current_user.id), exercise_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE spaced_repetition_items
                    SET repetitions=repetitions+1,
                        interval_days=GREATEST(1,ROUND(interval_days*ease_factor)),
                        next_review_date=CURRENT_DATE+GREATEST(1,ROUND(interval_days*ease_factor)),
                        last_reviewed_at=NOW()
                    WHERE user_id=%s AND exercise_id=%s
                    """,
                    (str(current_user.id), exercise_id),
                )

        conn.commit()
        return {"exercises_seen": new_seen, "score_pct": new_score, "status": new_status}


# ─── Skill Tree ───────────────────────────────────────────────────────────────

@router.get("/learning-path/skill-tree", tags=["Learning Path"])
def get_skill_tree(
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if not _has_active_premium(str(current_user.id), conn):
        raise HTTPException(status_code=403, detail="Skill tree necesită abonament Premium.")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT lpn.id, lpn.topic_key, lpn.topic_label, lpn.subiect_num,
                   lpn.status, lpn.score_pct, lpn.exercises_seen,
                   lpn.exercises_correct, lpn.target_exercises,
                   lpn.diagnostic_score_pct, lpn.priority, lpn.sort_order
            FROM learning_path_nodes lpn
            JOIN learning_paths lp ON lp.id = lpn.path_id
            WHERE lp.user_id = %s
            ORDER BY lpn.sort_order
            """,
            (str(current_user.id),),
        )
        nodes = cur.fetchall()

    by_subiect: dict = {}
    for node in nodes:
        s = node["subiect_num"]
        by_subiect.setdefault(s, []).append(dict(node))

    return {
        "subiects": [
            {
                "subiect": s,
                "label": f"Subiectul {s}",
                "topics": topics,
                "mastered": sum(1 for t in topics if t["status"] == "mastered"),
                "total": len(topics),
            }
            for s, topics in sorted(by_subiect.items())
        ]
    }


# ─── Spaced Repetition ────────────────────────────────────────────────────────

@router.post("/spaced-repetition/review", tags=["Learning Path"])
def submit_sr_review(
    body: dict,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if not _has_active_premium(str(current_user.id), conn):
        raise HTTPException(status_code=403, detail="Spaced repetition necesită abonament Premium.")

    exercise_id = body.get("exercise_id")
    quality = max(0, min(5, int(body.get("quality", 3))))

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM spaced_repetition_items WHERE user_id=%s AND exercise_id=%s",
            (str(current_user.id), exercise_id),
        )
        item = cur.fetchone()
        cur_interval = item["interval_days"] if item else 1
        cur_reps = item["repetitions"] if item else 0
        cur_ease = item["ease_factor"] if item else 2.5

        new_interval, new_reps, new_ease = _sm2(cur_interval, cur_reps, cur_ease, quality)
        next_date = date.today() + timedelta(days=new_interval)

        cur.execute(
            """
            INSERT INTO spaced_repetition_items
              (user_id, exercise_id, interval_days, repetitions, ease_factor,
               next_review_date, last_reviewed_at)
            VALUES (%s,%s,%s,%s,%s,%s,NOW())
            ON CONFLICT (user_id, exercise_id) DO UPDATE
            SET interval_days=%s, repetitions=%s, ease_factor=%s,
                next_review_date=%s, last_reviewed_at=NOW()
            """,
            (
                str(current_user.id), exercise_id,
                new_interval, new_reps, new_ease, next_date,
                new_interval, new_reps, new_ease, next_date,
            ),
        )
        conn.commit()

    return {
        "next_review_date": str(next_date),
        "interval_days": new_interval,
        "ease_factor": round(new_ease, 2),
    }
