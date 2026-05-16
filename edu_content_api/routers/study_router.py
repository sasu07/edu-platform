import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from psycopg.rows import dict_row

from auth import get_current_user
from database import get_db_conn
from models import (
    StudyPlanDayCreateRequest,
    StudySessionCompleteRequest,
    StudySessionStartRequest,
    UserDB,
    UserRole,
)
from services.xp_service import award_xp

router = APIRouter()


def _normalize_subiect_tag(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().upper()
    mapping = {"S1": "1", "S2": "2", "S3": "3", "1": "1", "2": "2", "3": "3"}
    return mapping.get(normalized, value)


def _build_session_selection(filters: dict, ex_count: int) -> tuple[str, list]:
    conditions = [
        "e.status = 'READY'",
        "e.metadata::jsonb->>'parent_external_id' IS NULL",
        "(e.metadata::jsonb->>'is_container' IS NULL OR (e.metadata::jsonb->>'is_container')::boolean = false)",
    ]
    params: list = []

    subiect_tag = _normalize_subiect_tag(filters.get("subiect_tag"))
    if subiect_tag:
        conditions.append(
            """
            EXISTS (
                SELECT 1 FROM exercise_tags et2
                JOIN tags t2 ON et2.tag_id = t2.id
                WHERE et2.exercise_id = e.id
                  AND t2.namespace = 'subiect'
                  AND t2.key = %s
            )
            """
        )
        params.append(subiect_tag)

    where_clause = " WHERE " + " AND ".join(conditions)
    query = f"""
        SELECT * FROM (
            SELECT DISTINCT e.id, e.statement_latex, e.statement_text,
                   e.answer_latex, e.answer_numeric_value, e.answer_numeric_expression,
                   e.solution_latex, e.difficulty, e.metadata
            FROM exercises e{where_clause}
        ) study_candidates
        ORDER BY RANDOM() LIMIT {ex_count}
    """
    return query, params


def _load_exact_exercise_set(conn: Connection, user_id: str, exercise_set_id: str):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT s.id as set_id, s.name, s.filters,
                   e.id as exercise_id, e.statement_latex, e.statement_text,
                   e.answer_latex, e.answer_numeric_value, e.answer_numeric_expression,
                   e.solution_latex, e.difficulty, e.metadata
            FROM user_exercise_sets s
            JOIN user_exercise_set_items si ON si.set_id = s.id
            JOIN exercises e ON e.id = si.exercise_id
            WHERE s.id = %s AND s.user_id = %s
            ORDER BY si.sort_order
            """,
            (exercise_set_id, user_id),
        )
        rows = cur.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="Setul selectat nu există sau nu îți aparține")

    set_filters = rows[0]["filters"] if rows[0]["filters"] else {}
    exercises = [
        {
            "id": row["exercise_id"],
            "statement_latex": row["statement_latex"],
            "statement_text": row["statement_text"],
            "answer_latex": row["answer_latex"],
            "answer_numeric_value": row["answer_numeric_value"],
            "answer_numeric_expression": row["answer_numeric_expression"],
            "solution_latex": row["solution_latex"],
            "difficulty": row["difficulty"],
            "metadata": row["metadata"],
        }
        for row in rows
    ]
    return rows[0]["set_id"], set_filters, exercises


def _ensure_parent_link(conn: Connection, parent_id: str, student_id: str) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id FROM parent_student WHERE parent_id=%s AND student_id=%s",
            (parent_id, student_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=403, detail="Nu ești legat de acest elev")


@router.post("/study-sessions/start", tags=["Study"])
def start_study_session(
    body: StudySessionStartRequest,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role not in (UserRole.STUDENT,):
        raise HTTPException(status_code=403, detail="Doar elevii pot porni sesiuni de studiu")

    session_type = body.session_type
    filters = body.filters
    ex_count = 10 if session_type == "test_scurt" else 25

    with conn.cursor(row_factory=dict_row) as cur:
        exact_set_id = filters.get("exercise_set_id")
        if exact_set_id:
            set_id, set_filters, exercises = _load_exact_exercise_set(conn, str(current_user.id), str(exact_set_id))
            filters = {**set_filters, **filters}
        else:
            query, params = _build_session_selection(filters, ex_count)
            cur.execute(query, params)
            exercises = cur.fetchall()
            set_id = None

        if not exercises:
            raise HTTPException(status_code=400, detail="Nu există exerciții disponibile pentru filtrele selectate")

        exercise_ids = [str(exercise["id"]) for exercise in exercises]

        if not set_id:
            cur.execute(
                """INSERT INTO user_exercise_sets (user_id, name, linked_plan, filters)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (str(current_user.id), f"Sesiune {session_type}", "study_session", json.dumps(filters)),
            )
            set_id = cur.fetchone()["id"]

            for exercise_id in exercise_ids:
                cur.execute(
                    "INSERT INTO user_exercise_set_items (set_id, exercise_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (str(set_id), exercise_id),
                )

        avg_diff = sum(ex["difficulty"] for ex in exercises if ex["difficulty"]) / max(
            1, sum(1 for ex in exercises if ex["difficulty"])
        )
        avg_diff = round(avg_diff, 2) if avg_diff else None

        cur.execute(
            """INSERT INTO study_sessions
               (user_id, session_type, filters, exercise_set_id, status,
                exercises_total, avg_difficulty)
               VALUES (%s, %s, %s, %s, 'active', %s, %s)
               RETURNING *""",
            (
                str(current_user.id),
                session_type,
                json.dumps(filters),
                str(set_id),
                len(exercise_ids),
                avg_diff,
            ),
        )
        session = dict(cur.fetchone())

        if body.plan_day_id:
            cur.execute(
                """
                UPDATE study_plan_days
                SET session_id = %s
                WHERE id = %s AND user_id = %s
                """,
                (str(session["id"]), str(body.plan_day_id), str(current_user.id)),
            )
        conn.commit()

    session["exercises"] = [dict(exercise) for exercise in exercises]
    return session


@router.post("/study-sessions/{session_id}/complete", tags=["Study"])
def complete_study_session(
    session_id: str,
    body: StudySessionCompleteRequest,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role not in (UserRole.STUDENT, UserRole.SCHOOL_TEACHER):
        raise HTTPException(status_code=403, detail="Acces interzis")

    exercises_completed = body.exercises_completed
    duration_sec = body.duration_sec

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM study_sessions WHERE id=%s AND user_id=%s",
            (session_id, str(current_user.id)),
        )
        session = cur.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Sesiune inexistentă")
        if session["status"] != "active":
            raise HTTPException(status_code=400, detail="Sesiunea nu este activă")

        completion_pct = exercises_completed / max(session["exercises_total"], 1)
        bonus_xp = 0
        if completion_pct >= 0.8:
            bonus_xp = 50 if session["session_type"] == "test_bac" else 20
            award_xp(conn, str(current_user.id), bonus_xp, "session_complete", session_id)

        cur.execute(
            """UPDATE study_sessions
               SET status='completed', completed_at=NOW(),
                   duration_sec=%s, exercises_completed=%s, xp_gained=%s
               WHERE id=%s RETURNING *""",
            (duration_sec, exercises_completed, bonus_xp, session_id),
        )
        updated = cur.fetchone()

        cur.execute(
            "UPDATE study_plan_days SET completed=TRUE, session_id=%s WHERE session_id IS NULL AND user_id=%s AND plan_date=CURRENT_DATE AND completed=FALSE",
            (session_id, str(current_user.id)),
        )

        conn.commit()

    return dict(updated)


@router.post("/study-sessions/{session_id}/abandon", tags=["Study"])
def abandon_study_session(
    session_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "UPDATE study_sessions SET status='abandoned', completed_at=NOW() WHERE id=%s AND user_id=%s RETURNING id",
            (session_id, str(current_user.id)),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Sesiune inexistentă")
        conn.commit()
    return {"status": "abandoned"}


@router.get("/study-sessions/", tags=["Study"])
def list_study_sessions(
    limit: int = 30,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT * FROM study_sessions
               WHERE user_id=%s ORDER BY started_at DESC LIMIT %s""",
            (str(current_user.id), limit),
        )
        return cur.fetchall()


@router.get("/study-sessions/{session_id}", tags=["Study"])
def get_study_session(
    session_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT * FROM study_sessions WHERE id=%s AND user_id=%s",
            (session_id, str(current_user.id)),
        )
        session = cur.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Sesiune inexistentă")

        if session["exercise_set_id"]:
            cur.execute(
                """SELECT e.id, e.statement_latex, e.statement_text, e.difficulty, e.points,
                          e.metadata, e.solution_latex, e.answer_latex,
                          e.answer_numeric_value, e.answer_numeric_expression
                   FROM user_exercise_set_items si
                   JOIN exercises e ON e.id = si.exercise_id
                   WHERE si.set_id=%s""",
                (str(session["exercise_set_id"]),),
            )
            exercises = cur.fetchall()
        else:
            exercises = []

        result = dict(session)
        result["exercises"] = exercises
        return result


@router.get("/student/study-stats", tags=["Study"])
def get_student_study_stats(
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    user_id = str(current_user.id)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT
                COUNT(*) as total_sessions,
                COUNT(*) FILTER (WHERE status='completed') as completed_sessions,
                SUM(duration_sec) FILTER (WHERE status='completed') as total_time_sec,
                SUM(exercises_completed) FILTER (WHERE status='completed') as total_exercises,
                ROUND(AVG(avg_difficulty) FILTER (WHERE status='completed'), 1) as avg_difficulty,
                SUM(xp_gained) as total_xp
               FROM study_sessions WHERE user_id=%s""",
            (user_id,),
        )
        totals = cur.fetchone()

        cur.execute(
            """SELECT
                DATE(started_at) as date,
                COUNT(*) as sessions,
                SUM(exercises_completed) as exercises,
                SUM(duration_sec) as time_sec
               FROM study_sessions
               WHERE user_id=%s AND started_at >= NOW() - INTERVAL '30 days'
               GROUP BY DATE(started_at)
               ORDER BY date""",
            (user_id,),
        )
        daily = cur.fetchall()

        cur.execute(
            """SELECT
                e.metadata->>'subiect' as subiect,
                COUNT(*) as total_available
               FROM exercises e
               WHERE e.status='READY' AND e.metadata->>'subiect' IS NOT NULL
               AND e.metadata::jsonb->>'parent_external_id' IS NULL
               GROUP BY e.metadata->>'subiect'""",
        )
        available_by_subiect = {row["subiect"]: row["total_available"] for row in cur.fetchall()}

        cur.execute(
            """SELECT e.metadata->>'subiect' as subiect, COUNT(*) as completed
               FROM student_progress sp
               JOIN exercises e ON e.id = sp.exercise_id
               WHERE sp.student_id=%s AND sp.completed=TRUE
               AND e.metadata->>'subiect' IS NOT NULL
               GROUP BY e.metadata->>'subiect'""",
            (user_id,),
        )
        completed_by_subiect = {row["subiect"]: row["completed"] for row in cur.fetchall()}

        subiect_progress = []
        for subject in ["1", "2", "3"]:
            total = available_by_subiect.get(subject, 0)
            done = completed_by_subiect.get(subject, 0)
            subiect_progress.append(
                {
                    "subiect": subject,
                    "label": f"Subiectul {subject}",
                    "total": total,
                    "completed": done,
                    "pct": round(done / total * 100) if total > 0 else 0,
                }
            )

        recommendation = min(subiect_progress, key=lambda item: item["pct"]) if subiect_progress else None
        totals_dict = dict(totals) if totals else {}
        completed_sessions = totals_dict.get("completed_sessions") or 0
        total_sessions = totals_dict.get("total_sessions") or 0
        avg_completion_pct = round((completed_sessions / total_sessions) * 100) if total_sessions > 0 else 0

        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "total_time_sec": totals_dict.get("total_time_sec") or 0,
            "total_exercises": totals_dict.get("total_exercises") or 0,
            "avg_difficulty": totals_dict.get("avg_difficulty"),
            "total_xp": totals_dict.get("total_xp") or 0,
            "avg_completion_pct": avg_completion_pct,
            "daily_last_30": [dict(day) for day in daily],
            "subiect_progress": subiect_progress,
            "recommendation": recommendation["label"] if recommendation else None,
        }


@router.get("/parent/students/{student_id}/study-sessions", tags=["Parent"])
def get_student_study_sessions_for_parent(
    student_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role not in (UserRole.PARENT, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")

    if current_user.role == UserRole.PARENT:
        _ensure_parent_link(conn, str(current_user.id), student_id)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT * FROM study_sessions
               WHERE user_id=%s ORDER BY started_at DESC LIMIT 60""",
            (student_id,),
        )
        sessions = cur.fetchall()

        cur.execute(
            """SELECT
                COUNT(*) FILTER (WHERE status='completed') as completed,
                SUM(exercises_completed) FILTER (WHERE status='completed') as total_exercises,
                SUM(duration_sec) FILTER (WHERE status='completed') as total_time_sec
               FROM study_sessions WHERE user_id=%s""",
            (student_id,),
        )
        stats = cur.fetchone()

        return {"sessions": [dict(session) for session in sessions], "stats": dict(stats) if stats else {}}


@router.get("/parent/students/{student_id}/study-plan", tags=["Parent"])
def get_student_study_plan_for_parent(
    student_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role not in (UserRole.PARENT, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")

    if current_user.role == UserRole.PARENT:
        _ensure_parent_link(conn, str(current_user.id), student_id)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT spd.*, u.full_name as teacher_name
               FROM study_plan_days spd
               LEFT JOIN users u ON u.id = spd.teacher_id
               WHERE spd.user_id=%s AND spd.plan_date >= CURRENT_DATE - INTERVAL '30 days'
               ORDER BY spd.plan_date, spd.created_at""",
            (student_id,),
        )
        return cur.fetchall()


@router.get("/study-plan/", tags=["Study"])
def get_study_plan(
    student_id: Optional[str] = None,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if student_id and current_user.role in (UserRole.TEACHER, UserRole.ADMIN):
        target_id = student_id
    else:
        target_id = str(current_user.id)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT spd.*, u.full_name as teacher_name
               FROM study_plan_days spd
               LEFT JOIN users u ON u.id = spd.teacher_id
               WHERE spd.user_id=%s AND spd.plan_date >= CURRENT_DATE - INTERVAL '1 day'
               ORDER BY spd.plan_date, spd.created_at""",
            (target_id,),
        )
        return cur.fetchall()


@router.post("/study-plan/", tags=["Study"])
def create_study_plan_day(
    body: StudyPlanDayCreateRequest,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    plan_date = body.plan_date
    session_type = body.session_type
    filters = body.filters
    note = body.note
    target_student_id = body.user_id or body.student_id

    if current_user.role in (UserRole.TEACHER, UserRole.ADMIN) and target_student_id:
        target_user_id = target_student_id
        created_by = "teacher"
        teacher_id = str(current_user.id)
    else:
        target_user_id = str(current_user.id)
        created_by = "student"
        teacher_id = None

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """INSERT INTO study_plan_days
               (user_id, plan_date, session_type, filters, note, created_by, teacher_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               RETURNING *""",
            (
                target_user_id,
                plan_date,
                session_type,
                json.dumps(filters),
                note,
                created_by,
                teacher_id,
            ),
        )
        row = cur.fetchone()

        if created_by == "teacher":
            cur.execute(
                """INSERT INTO notifications (user_id, type, title, body, related_id)
                   VALUES (%s, 'study_plan', %s, %s, %s)""",
                (
                    target_user_id,
                    "Plan de studiu nou 📅",
                    f"Profesorul ți-a adăugat o sesiune în plan pentru {plan_date}.",
                    str(row["id"]),
                ),
            )

        conn.commit()
    return dict(row)


@router.delete("/study-plan/{plan_id}", tags=["Study"])
def delete_study_plan_day(
    plan_id: str,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    with conn.cursor(row_factory=dict_row) as cur:
        if current_user.role in (UserRole.TEACHER, UserRole.ADMIN):
            cur.execute("DELETE FROM study_plan_days WHERE id=%s RETURNING id", (plan_id,))
        else:
            cur.execute(
                "DELETE FROM study_plan_days WHERE id=%s AND user_id=%s RETURNING id",
                (plan_id, str(current_user.id)),
            )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Intrare inexistentă")
        conn.commit()
    return {"deleted": True}


@router.get("/teacher/students-list", tags=["Teacher"])
def get_students_list(
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role not in (UserRole.TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, full_name, email FROM users WHERE role='student' AND is_active=TRUE ORDER BY full_name"
        )
        return cur.fetchall()
