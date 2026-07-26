import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import Connection
from psycopg.rows import dict_row

from ai_plan_service import generate_hints, generate_hints_fallback
from ai_tagger import get_ai_tagger
from answer_numeric import evaluate_numeric_answer
from auth import get_current_user, require_staff
from database import get_db_conn
from models import (
    ExerciseCreate,
    ExerciseDB,
    ExerciseSetCreateRequest,
    ExerciseSetUpdateRequest,
    ExerciseUpdate,
    TagCreate,
    TagDB,
    UserDB,
    UserRole,
)

router = APIRouter()


def _open_review_item(conn: Connection, student_id: str, exercise_id: str, source_reason: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO exercise_review_items
                (student_id, exercise_id, status, source_reason, fail_count, revisit_count, first_flagged_at, last_flagged_at, resolved_at)
            VALUES
                (%s, %s, 'open', %s, 0, 1, NOW(), NOW(), NULL)
            ON CONFLICT (student_id, exercise_id) DO UPDATE
            SET status='open',
                source_reason=EXCLUDED.source_reason,
                revisit_count=exercise_review_items.revisit_count + 1,
                last_flagged_at=NOW(),
                resolved_at=NULL
            """,
            (student_id, exercise_id, source_reason),
        )


def _resolve_review_item(conn: Connection, student_id: str, exercise_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE exercise_review_items
            SET status='resolved', resolved_at=NOW()
            WHERE student_id=%s AND exercise_id=%s AND status='open'
            """,
            (student_id, exercise_id),
        )


def create_exercise_record(exercise: ExerciseCreate, conn: Connection) -> dict:
    answer_numeric_value, answer_numeric_expression = evaluate_numeric_answer(exercise.answer_latex)
    query = """
    INSERT INTO exercises (
        exam_type, profile, subject_part, item_type, statement_latex, statement_text,
        answer_latex, answer_numeric_value, answer_numeric_expression,
        solution_latex, scoring_guide_latex, scoring_guide_text,
        difficulty, estimated_time_sec, points, metadata, status, created_by_user_id
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id, exam_type, profile, subject_part, item_type, statement_latex, statement_text,
              answer_latex, answer_numeric_value, answer_numeric_expression,
              solution_latex, scoring_guide_latex, scoring_guide_text,
              difficulty, estimated_time_sec, points, metadata, status, created_by_user_id,
              created_at, updated_at;
    """
    with conn.cursor(row_factory=dict_row) as cur:
        exam_type_value = exercise.exam_type.value if hasattr(exercise.exam_type, "value") else exercise.exam_type
        subject_part_value = exercise.subject_part.value if exercise.subject_part and hasattr(exercise.subject_part, "value") else exercise.subject_part
        item_type_value = exercise.item_type.value if exercise.item_type and hasattr(exercise.item_type, "value") else exercise.item_type
        status_value = exercise.status.value if hasattr(exercise.status, "value") else exercise.status
        metadata_json = json.dumps(exercise.metadata) if exercise.metadata else None

        cur.execute(
            query,
            (
                exam_type_value,
                exercise.profile,
                subject_part_value,
                item_type_value,
                exercise.statement_latex,
                exercise.statement_text,
                exercise.answer_latex,
                answer_numeric_value,
                answer_numeric_expression,
                exercise.solution_latex,
                exercise.scoring_guide_latex,
                exercise.scoring_guide_text,
                exercise.difficulty,
                exercise.estimated_time_sec,
                exercise.points,
                metadata_json,
                status_value,
                exercise.created_by_user_id,
            ),
        )
        new_exercise = cur.fetchone()
        conn.commit()
        return new_exercise


def tag_exercise_in_db(exercise_id: uuid.UUID, conn: Connection) -> dict:
    query = "SELECT statement_text, solution_latex FROM exercises WHERE id = %s;"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (exercise_id,))
        exercise = cur.fetchone()

    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")

    tagger = get_ai_tagger()
    tags = tagger.tag_exercise(exercise["statement_text"], exercise["solution_latex"])

    results = []
    for tag in tags:
        tag_query = """
        INSERT INTO tags (namespace, key, label)
        VALUES (%s, %s, %s)
        ON CONFLICT (namespace, key) DO UPDATE SET label = EXCLUDED.label
        RETURNING id;
        """
        with conn.cursor() as cur:
            cur.execute(tag_query, (tag["namespace"], tag["key"], tag["label"]))
            res = cur.fetchone()
            if not res:
                continue
            tag_id = res["id"] if isinstance(res, dict) else res[0]
            link_query = """
            INSERT INTO exercise_tags (exercise_id, tag_id, weight, confidence, created_by)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (exercise_id, tag_id) DO UPDATE SET weight = EXCLUDED.weight
            RETURNING tag_id;
            """
            cur.execute(link_query, (exercise_id, tag_id, tag.get("weight", 1.0), 0.8, "model"))
            cur.fetchone()
        results.append(tag)

    conn.commit()
    return {"status": "success", "tags_applied": results}


@router.post("/exercises/", response_model=ExerciseDB, status_code=status.HTTP_201_CREATED)
def create_exercise(exercise: ExerciseCreate, conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    try:
        return create_exercise_record(exercise, conn)
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Eroare internă de server")


@router.get("/exercises/", response_model=List[ExerciseDB])
def read_exercises(
    exam_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    subiect_tag: Optional[str] = None,
    topic_tag: Optional[str] = None,
    method_tag: Optional[str] = None,
    difficulty_min: Optional[int] = None,
    difficulty_max: Optional[int] = None,
    has_solution: Optional[bool] = None,
    has_scoring_guide: Optional[bool] = None,
    subject_part: Optional[str] = None,
    profile: Optional[str] = None,
    year: Optional[int] = None,
    only_roots: Optional[bool] = None,
    exclude_seen: Optional[bool] = None,
    is_container: Optional[bool] = None,
    limit: Optional[int] = None,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    conditions = []
    params: list = []

    if exam_type:
        conditions.append("e.exam_type = %s")
        params.append(exam_type)

    if status_filter:
        conditions.append("e.status = %s")
        params.append(status_filter)
    else:
        conditions.append("(e.status != 'ARCHIVED' OR e.status IS NULL)")

    if subject_part:
        conditions.append("e.subject_part = %s")
        params.append(subject_part)

    if profile:
        conditions.append("e.profile = %s")
        params.append(profile)

    if difficulty_min is not None:
        conditions.append("(e.difficulty >= %s OR e.difficulty IS NULL)")
        params.append(difficulty_min)

    if difficulty_max is not None:
        conditions.append("(e.difficulty <= %s OR e.difficulty IS NULL)")
        params.append(difficulty_max)

    if has_solution:
        conditions.append("(e.solution_latex IS NOT NULL OR e.answer_latex IS NOT NULL)")

    if has_scoring_guide:
        conditions.append("(e.scoring_guide_latex IS NOT NULL OR e.scoring_guide_text IS NOT NULL)")

    if only_roots:
        conditions.append("e.metadata::jsonb->>'parent_external_id' IS NULL")

    if is_container is True:
        conditions.append("(e.metadata::jsonb->>'is_container')::boolean = true")
    elif is_container is False:
        conditions.append("(e.metadata::jsonb->>'is_container' IS NULL OR (e.metadata::jsonb->>'is_container')::boolean = false)")

    conditions_no_seen = list(conditions)
    params_no_seen: list = list(params)

    if exclude_seen and current_user:
        conditions.append(
            """
            e.id NOT IN (
                SELECT exercise_id FROM user_seen_exercises WHERE user_id = %s
            )
            """
        )
        params.append(str(current_user.id))

    def _add(cond, param=None):
        conditions.append(cond)
        conditions_no_seen.append(cond)
        if param is not None:
            params.append(param)
            params_no_seen.append(param)

    if year:
        _add(
            """
            EXISTS (
                SELECT 1 FROM exercise_source_segments ess
                JOIN source_segments sg ON sg.id = ess.source_segment_id
                JOIN sources s ON s.id = sg.source_id
                WHERE ess.exercise_id = e.id AND s.year = %s
            )
            """,
            year,
        )

    if subiect_tag:
        _add(
            """
            EXISTS (
                SELECT 1 FROM exercise_tags et2
                JOIN tags t2 ON et2.tag_id = t2.id
                WHERE et2.exercise_id = e.id
                  AND t2.namespace = 'subiect'
                  AND t2.key = %s
            )
            """,
            subiect_tag,
        )

    if topic_tag:
        _add(
            """
            EXISTS (
                SELECT 1 FROM exercise_tags et3
                JOIN tags t3 ON et3.tag_id = t3.id
                WHERE et3.exercise_id = e.id
                  AND t3.namespace = 'topic'
                  AND t3.key = %s
            )
            """,
            topic_tag,
        )

    if method_tag:
        _add(
            """
            EXISTS (
                SELECT 1 FROM exercise_tags et4
                JOIN tags t4 ON et4.tag_id = t4.id
                WHERE et4.exercise_id = e.id
                  AND t4.namespace = 'method'
                  AND t4.key = %s
            )
            """,
            method_tag,
        )

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    if limit:
        query = f"""
        SELECT * FROM (
            SELECT DISTINCT e.id, e.exam_type, e.profile, e.subject_part, e.item_type,
                   e.statement_latex, e.statement_text,
                   e.answer_latex, e.solution_latex, e.scoring_guide_latex, e.scoring_guide_text,
                   e.difficulty, e.estimated_time_sec, e.points, e.metadata, e.status,
                   e.created_by_user_id, e.created_at, e.updated_at
            FROM exercises e{where_clause}
        ) sub
        ORDER BY RANDOM() LIMIT {int(limit)};
        """
    else:
        query = f"""
        SELECT DISTINCT e.id, e.exam_type, e.profile, e.subject_part, e.item_type,
               e.statement_latex, e.statement_text,
               e.answer_latex, e.solution_latex, e.scoring_guide_latex, e.scoring_guide_text,
               e.difficulty, e.estimated_time_sec, e.points, e.metadata, e.status,
               e.created_by_user_id, e.created_at, e.updated_at
        FROM exercises e{where_clause}
        ORDER BY e.created_at DESC;
        """

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, tuple(params))
        exercises = cur.fetchall()

        if len(exercises) == 0 and exclude_seen and current_user:
            fallback_where = " WHERE " + " AND ".join(conditions_no_seen) if conditions_no_seen else ""
            if limit:
                fallback_query = f"""
                SELECT * FROM (
                    SELECT DISTINCT e.id, e.exam_type, e.profile, e.subject_part, e.item_type,
                           e.statement_latex, e.statement_text,
                           e.answer_latex, e.solution_latex, e.scoring_guide_latex, e.scoring_guide_text,
                           e.difficulty, e.estimated_time_sec, e.points, e.metadata, e.status,
                           e.created_by_user_id, e.created_at, e.updated_at
                    FROM exercises e{fallback_where}
                ) sub
                ORDER BY RANDOM() LIMIT {int(limit)};
                """
            else:
                fallback_query = f"""
                SELECT * FROM (
                    SELECT DISTINCT e.id, e.exam_type, e.profile, e.subject_part, e.item_type,
                           e.statement_latex, e.statement_text,
                           e.answer_latex, e.solution_latex, e.scoring_guide_latex, e.scoring_guide_text,
                           e.difficulty, e.estimated_time_sec, e.points, e.metadata, e.status,
                           e.created_by_user_id, e.created_at, e.updated_at
                    FROM exercises e{fallback_where}
                ) sub
                ORDER BY RANDOM();
                """
            cur.execute(fallback_query, tuple(params_no_seen))
            exercises = cur.fetchall()

        return exercises


@router.get("/exercises/with-tags")
def read_exercises_with_tags(
    conn: Connection = Depends(get_db_conn),
    _user: UserDB = Depends(get_current_user),
):
    """Lista de exerciții pentru administrare, cu tag-urile INCLUSE, într-un singur query.
    Înlocuiește N+1-ul din ExerciseList (o cerere /tags per exercițiu → 5000+ cereri) +
    payload ușor (fără soluție/barem/metadata — lista arată doar enunțul)."""
    query = """
    SELECT e.id, e.exam_type, e.profile, e.subject_part, e.item_type,
           e.statement_text, e.statement_latex, e.difficulty, e.points, e.status,
           e.created_at, e.updated_at,
           COALESCE(
             (SELECT json_agg(json_build_object(
                        'id', t.id, 'namespace', t.namespace, 'key', t.key,
                        'label', t.label, 'weight', et.weight)
                      ORDER BY t.namespace, t.key)
              FROM exercise_tags et JOIN tags t ON t.id = et.tag_id
              WHERE et.exercise_id = e.id),
             '[]'::json
           ) AS tags
    FROM exercises e
    WHERE (e.status != 'ARCHIVED' OR e.status IS NULL)
    ORDER BY e.created_at DESC;
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query)
        return cur.fetchall()


@router.get("/exercises/filter-options")
def get_exercise_filter_options(
    subiect_tag: Optional[str] = None,
    profile: Optional[str] = None,
    year: Optional[int] = None,
    topic_tag: Optional[str] = None,
    conn: Connection = Depends(get_db_conn),
    _user: UserDB = Depends(get_current_user),
):
    conditions = ["(e.status != 'ARCHIVED' OR e.status IS NULL)"]
    params: list = []

    if subiect_tag:
        conditions.append(
            """
            EXISTS (
                SELECT 1 FROM exercise_tags et2
                JOIN tags t2 ON et2.tag_id = t2.id
                WHERE et2.exercise_id = e.id AND t2.namespace = 'subiect' AND t2.key = %s
            )
            """
        )
        params.append(subiect_tag)

    if profile:
        conditions.append("e.profile = %s")
        params.append(profile)

    if year:
        conditions.append(
            """
            EXISTS (
                SELECT 1 FROM exercise_source_segments ess
                JOIN source_segments sg ON sg.id = ess.source_segment_id
                JOIN sources s ON s.id = sg.source_id
                WHERE ess.exercise_id = e.id AND s.year = %s
            )
            """
        )
        params.append(year)

    if topic_tag:
        conditions.append(
            """
            EXISTS (
                SELECT 1 FROM exercise_tags et3
                JOIN tags t3 ON et3.tag_id = t3.id
                WHERE et3.exercise_id = e.id AND t3.namespace = 'topic' AND t3.key = %s
            )
            """
        )
        params.append(topic_tag)

    where = "WHERE " + " AND ".join(conditions)
    base_ids = f"SELECT e.id FROM exercises e {where}"

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT DISTINCT profile FROM exercises WHERE profile IS NOT NULL ORDER BY profile")
        profiles = [row["profile"] for row in cur.fetchall()]

        cur.execute(
            """
            SELECT DISTINCT s.year FROM sources s
            JOIN source_segments sg ON sg.source_id = s.id
            JOIN exercise_source_segments ess ON ess.source_segment_id = sg.id
            WHERE s.year IS NOT NULL ORDER BY s.year DESC
            """
        )
        years = [row["year"] for row in cur.fetchall()]

        cur.execute(
            f"""
            SELECT t.key, t.label, COUNT(DISTINCT et.exercise_id) as cnt
            FROM tags t
            JOIN exercise_tags et ON et.tag_id = t.id
            WHERE t.namespace = 'topic'
              AND et.exercise_id IN ({base_ids})
            GROUP BY t.key, t.label
            ORDER BY cnt DESC
            """,
            tuple(params),
        )
        topics = [{"key": row["key"], "label": row["label"], "count": row["cnt"]} for row in cur.fetchall()]

        cur.execute(
            f"""
            SELECT t.key, t.label, COUNT(DISTINCT et.exercise_id) as cnt
            FROM tags t
            JOIN exercise_tags et ON et.tag_id = t.id
            WHERE t.namespace = 'method'
              AND et.exercise_id IN ({base_ids})
            GROUP BY t.key, t.label
            ORDER BY cnt DESC
            LIMIT 30
            """,
            tuple(params),
        )
        methods = [{"key": row["key"], "label": row["label"], "count": row["cnt"]} for row in cur.fetchall()]

    return {"profiles": profiles, "years": years, "topics": topics, "methods": methods}


@router.get("/exercises/batch-children")
def get_exercises_batch_children(ids: str, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    id_list = [item.strip() for item in ids.split(",") if item.strip()]
    if not id_list:
        return {}
    try:
        parsed_ids = [str(uuid.UUID(item)) for item in id_list]
    except ValueError:
        raise HTTPException(status_code=400, detail="IDs invalide")

    with conn.cursor(row_factory=dict_row) as cur:
        placeholders = ",".join(["%s"] * len(parsed_ids))
        cur.execute(
            f"SELECT id, metadata::jsonb->>'external_id' as ext_id FROM exercises WHERE id IN ({placeholders})",
            tuple(parsed_ids),
        )
        parents = cur.fetchall()
        ext_to_parent_id = {parent["ext_id"]: str(parent["id"]) for parent in parents if parent["ext_id"]}

        if not ext_to_parent_id:
            return {parent_id: [] for parent_id in parsed_ids}

        ext_ids = list(ext_to_parent_id.keys())
        ext_placeholders = ",".join(["%s"] * len(ext_ids))
        cur.execute(
            f"""SELECT id, exam_type, profile, subject_part, item_type,
                       statement_latex, statement_text, answer_latex, solution_latex,
                       scoring_guide_latex, scoring_guide_text,
                       difficulty, estimated_time_sec, points, metadata, status,
                       created_at, updated_at
                FROM exercises
                WHERE metadata::jsonb->>'parent_external_id' IN ({ext_placeholders})
                ORDER BY metadata::jsonb->>'subpoint' ASC""",
            tuple(ext_ids),
        )
        all_children = cur.fetchall()

    result: dict = {parent_id: [] for parent_id in parsed_ids}
    for child in all_children:
        parent_ext = child["metadata"].get("parent_external_id") if child["metadata"] else None
        if parent_ext and parent_ext in ext_to_parent_id:
            result[ext_to_parent_id[parent_ext]].append(child)
    return result


@router.get("/exercises/{exercise_id}", response_model=ExerciseDB)
def read_exercise(exercise_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    query = """
    SELECT id, exam_type, profile, subject_part, item_type, statement_latex, statement_text,
           answer_latex, solution_latex, scoring_guide_latex, scoring_guide_text,
           difficulty, estimated_time_sec, points, metadata, status, created_by_user_id,
           created_at, updated_at
    FROM exercises WHERE id = %s;
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (exercise_id,))
        exercise = cur.fetchone()
        if exercise is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
        return exercise


@router.get("/exercises/{exercise_id}/hints", tags=["Student"])
def get_exercise_hints(
    exercise_id: uuid.UUID,
    conn: Connection = Depends(get_db_conn),
    _user: UserDB = Depends(get_current_user),
):
    """
    Indicii progresive pentru un exercițiu. Generate o singură dată (AI, din
    enunț + soluție) și apoi servite din cache (tabel exercise_hints).
    Dacă AI-ul nu e disponibil, întoarce listă goală — fluxul nu se blochează.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT hints, source FROM exercise_hints WHERE exercise_id = %s",
            (str(exercise_id),),
        )
        cached = cur.fetchone()
    if cached and cached["hints"]:
        return {"exercise_id": str(exercise_id), "hints": cached["hints"], "source": cached["source"]}

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT statement_latex, statement_text, solution_latex, scoring_guide_latex FROM exercises WHERE id = %s",
            (str(exercise_id),),
        )
        ex = cur.fetchone()
    if not ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercițiu negăsit")

    statement = ex["statement_latex"] or ex["statement_text"] or ""
    solution = ex["solution_latex"] or ""
    scoring = ex["scoring_guide_latex"] or ""
    hints = generate_hints(statement, solution, scoring)

    if hints:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO exercise_hints (exercise_id, hints, source)
                VALUES (%s, %s, 'ai')
                ON CONFLICT (exercise_id) DO UPDATE
                SET hints = EXCLUDED.hints, source = 'ai', updated_at = NOW()
                """,
                (str(exercise_id), json.dumps(hints)),
            )
            conn.commit()
        return {"exercise_id": str(exercise_id), "hints": hints, "source": "ai"}

    # AI indisponibil → fallback din soluție. NU cache-uim: la primul apel cu
    # AI funcțional (cheie alimentată) se generează și se cache-uiește versiunea AI.
    fallback = generate_hints_fallback(solution, scoring)
    if fallback:
        return {"exercise_id": str(exercise_id), "hints": fallback, "source": "fallback"}

    return {"exercise_id": str(exercise_id), "hints": [], "source": "unavailable"}


@router.post("/exercises/{exercise_id}/review/open")
def open_exercise_review_item(
    exercise_id: uuid.UUID,
    reason: str = "blocked",
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role not in (UserRole.STUDENT, UserRole.SCHOOL_TEACHER):
        raise HTTPException(status_code=403, detail="Doar elevii pot salva exerciții pentru revizuire")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM exercises WHERE id=%s", (str(exercise_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Exercițiu inexistent")

    _open_review_item(conn, str(current_user.id), str(exercise_id), reason)
    conn.commit()
    return {"ok": True}


@router.post("/exercises/{exercise_id}/review/resolve")
def resolve_exercise_review_item(
    exercise_id: uuid.UUID,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role not in (UserRole.STUDENT, UserRole.SCHOOL_TEACHER):
        raise HTTPException(status_code=403, detail="Doar elevii pot gestiona jurnalul de revizuire")

    _resolve_review_item(conn, str(current_user.id), str(exercise_id))
    conn.commit()
    return {"ok": True}


@router.put("/exercises/{exercise_id}", response_model=ExerciseDB)
def update_exercise(exercise_id: uuid.UUID, exercise: ExerciseUpdate, conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    updates = []
    values = []
    update_data = exercise.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    if "answer_latex" in update_data and "answer_numeric_value" not in update_data and "answer_numeric_expression" not in update_data:
        numeric_value, numeric_expression = evaluate_numeric_answer(update_data.get("answer_latex"))
        update_data["answer_numeric_value"] = numeric_value
        update_data["answer_numeric_expression"] = numeric_expression

    for key, value in update_data.items():
        updates.append(f"{key} = %s")
        if hasattr(value, "value"):
            value = value.value
        if isinstance(value, dict):
            value = json.dumps(value)
        values.append(value)

    updates.append("updated_at = CURRENT_TIMESTAMP")
    values.append(exercise_id)
    query = f"""
    UPDATE exercises SET {', '.join(updates)}
    WHERE id = %s
    RETURNING id, exam_type, profile, subject_part, item_type, statement_latex, statement_text,
              answer_latex, answer_numeric_value, answer_numeric_expression,
              solution_latex, scoring_guide_latex, scoring_guide_text,
              difficulty, estimated_time_sec, points, metadata, status, created_by_user_id,
              created_at, updated_at;
    """
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, values)
            updated_exercise = cur.fetchone()
            conn.commit()
            if updated_exercise is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
            return updated_exercise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Eroare internă de server")


@router.delete("/exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(exercise_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    query = "DELETE FROM exercises WHERE id = %s RETURNING id;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (exercise_id,))
            deleted_count = cur.rowcount
            conn.commit()
            if deleted_count == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Eroare internă de server")


@router.post("/tags/", response_model=TagDB, status_code=status.HTTP_201_CREATED)
def create_tag(tag: TagCreate, conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    query = """
    INSERT INTO tags (namespace, key, label, parent_id)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (namespace, key) DO UPDATE SET label = EXCLUDED.label
    RETURNING id, namespace, key, label, parent_id, created_at;
    """
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (tag.namespace, tag.key, tag.label, tag.parent_id))
            new_tag = cur.fetchone()
            conn.commit()
            return new_tag
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Eroare internă de server")


@router.get("/tags/", response_model=List[TagDB])
def read_tags(namespace: Optional[str] = None, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    if namespace:
        query = "SELECT id, namespace, key, label, parent_id, created_at FROM tags WHERE namespace = %s ORDER BY namespace, key;"
        params = (namespace,)
    else:
        query = "SELECT id, namespace, key, label, parent_id, created_at FROM tags ORDER BY namespace, key;"
        params = ()

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        return cur.fetchall()


@router.post("/exercises/{exercise_id}/tag")
def tag_exercise_endpoint(exercise_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    try:
        return tag_exercise_in_db(exercise_id, conn)
    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error applying tags: {exc}")


@router.get("/exercises/{exercise_id}/tags")
def get_exercise_tags(exercise_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    query = """
    SELECT t.id, t.namespace, t.key, t.label, et.weight
    FROM exercise_tags et
    JOIN tags t ON et.tag_id = t.id
    WHERE et.exercise_id = %s
    ORDER BY t.namespace, t.key;
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (exercise_id,))
        return cur.fetchall()


@router.post("/exercises/{exercise_id}/tags/{tag_id}")
def add_tag_to_exercise(exercise_id: uuid.UUID, tag_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    query = """
    INSERT INTO exercise_tags (exercise_id, tag_id, weight, confidence, created_by)
    VALUES (%s, %s, 1.0, 1.0, 'manual')
    ON CONFLICT (exercise_id, tag_id) DO NOTHING
    RETURNING exercise_id;
    """
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, (exercise_id, tag_id))
            result = cur.fetchone()
            conn.commit()
            if result:
                return {"status": "added"}
            return {"status": "already_exists"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error adding tag: {exc}")


@router.delete("/exercises/{exercise_id}/tags/{tag_id}")
def remove_tag_from_exercise(exercise_id: uuid.UUID, tag_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _staff: UserDB = Depends(require_staff)):
    query = "DELETE FROM exercise_tags WHERE exercise_id = %s AND tag_id = %s;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (exercise_id, tag_id))
            conn.commit()
            return {"status": "removed"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error removing tag: {exc}")


@router.get("/exercises/{exercise_id}/children")
def get_exercise_children(exercise_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT metadata::jsonb->>'external_id' as external_id FROM exercises WHERE id = %s", (exercise_id,))
        parent = cur.fetchone()
        if not parent:
            raise HTTPException(status_code=404, detail="Exercițiul nu a fost găsit")

        parent_ext_id = parent["external_id"]
        if not parent_ext_id:
            return []

        cur.execute(
            """
            SELECT id, exam_type, profile, subject_part, item_type,
                   statement_latex, statement_text, answer_latex, solution_latex,
                   scoring_guide_latex, scoring_guide_text,
                   difficulty, estimated_time_sec, points, metadata, status,
                   created_at, updated_at
            FROM exercises
            WHERE metadata::jsonb->>'parent_external_id' = %s
            ORDER BY metadata::jsonb->>'subpoint' ASC
            """,
            (parent_ext_id,),
        )
        return cur.fetchall()


@router.get("/exercises/by-path/{path:path}")
def get_exercises_by_path(path: str, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT DISTINCT e.id, e.exam_type, e.profile, e.subject_part, e.item_type,
                   e.statement_latex, e.statement_text, e.difficulty,
                   e.points, e.metadata, e.status, e.created_at, e.updated_at,
                   e.metadata::jsonb->>'path' as path_sort
            FROM exercises e
            JOIN exercise_tags et ON e.id = et.exercise_id
            JOIN tags t ON et.tag_id = t.id
            WHERE t.namespace = 'path'
              AND (t.key = %s OR t.key LIKE %s)
            ORDER BY path_sort ASC
            """,
            (path, path + "/%"),
        )
        return cur.fetchall()


@router.post("/exercise-sets/", tags=["ExerciseSets"])
def save_exercise_set(
    body: ExerciseSetCreateRequest,
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    exercise_ids = body.exercise_ids
    filters = body.filters
    name = body.name or f"Set {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    linked_plan = body.linked_plan

    if not exercise_ids:
        raise HTTPException(status_code=400, detail="exercise_ids este obligatoriu")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO user_exercise_sets (user_id, name, linked_plan, filters)
            VALUES (%s, %s, %s, %s)
            RETURNING id, user_id, name, linked_plan, filters, created_at
            """,
            (str(current_user.id), name, linked_plan, json.dumps(filters)),
        )
        new_set = cur.fetchone()
        set_id = new_set["id"]

        for idx, ex_id in enumerate(exercise_ids):
            cur.execute(
                "INSERT INTO user_exercise_set_items (set_id, exercise_id, sort_order) VALUES (%s, %s, %s)",
                (str(set_id), str(ex_id), idx),
            )

        for ex_id in exercise_ids:
            cur.execute(
                """
                INSERT INTO user_seen_exercises (user_id, exercise_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (str(current_user.id), str(ex_id)),
            )

        conn.commit()
    return {"id": str(set_id), "name": name, "exercise_count": len(exercise_ids)}


@router.get("/exercise-sets/", tags=["ExerciseSets"])
def list_exercise_sets(current_user: UserDB = Depends(get_current_user), conn: Connection = Depends(get_db_conn)):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT s.id, s.name, s.linked_plan, s.filters, s.created_at,
                   COUNT(i.id) AS exercise_count
            FROM user_exercise_sets s
            LEFT JOIN user_exercise_set_items i ON i.set_id = s.id
            WHERE s.user_id = %s
            GROUP BY s.id
            ORDER BY s.created_at DESC
            """,
            (str(current_user.id),),
        )
        rows = cur.fetchall()
    return [
        {
            "id": str(row["id"]),
            "name": row["name"],
            "linked_plan": row["linked_plan"],
            "filters": row["filters"],
            "exercise_count": row["exercise_count"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]


@router.get("/exercise-sets/{set_id}", tags=["ExerciseSets"])
def get_exercise_set(set_id: uuid.UUID, current_user: UserDB = Depends(get_current_user), conn: Connection = Depends(get_db_conn)):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, name, linked_plan, filters, created_at FROM user_exercise_sets WHERE id = %s AND user_id = %s",
            (str(set_id), str(current_user.id)),
        )
        exercise_set = cur.fetchone()
    if not exercise_set:
        raise HTTPException(status_code=404, detail="Set negăsit")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT e.id, e.exam_type, e.profile, e.subject_part, e.item_type,
                   e.statement_latex, e.statement_text,
                   e.answer_latex, e.solution_latex, e.scoring_guide_latex, e.scoring_guide_text,
                   e.difficulty, e.estimated_time_sec, e.points, e.metadata, e.status,
                   e.created_by_user_id, e.created_at, e.updated_at
            FROM user_exercise_set_items i
            JOIN exercises e ON e.id = i.exercise_id
            WHERE i.set_id = %s
            ORDER BY i.sort_order
            """,
            (str(set_id),),
        )
        exercises = cur.fetchall()

    return {
        "id": str(exercise_set["id"]),
        "name": exercise_set["name"],
        "linked_plan": exercise_set["linked_plan"],
        "filters": exercise_set["filters"],
        "created_at": exercise_set["created_at"].isoformat() if exercise_set["created_at"] else None,
        "exercises": exercises,
    }


@router.put("/exercise-sets/{set_id}", tags=["ExerciseSets"])
def update_exercise_set(
    set_id: uuid.UUID,
    body: ExerciseSetUpdateRequest,
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    updates = []
    values: list[str | None] = []

    if body.name is not None:
        updates.append("name = %s")
        values.append(body.name.strip() or f"Set {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    if body.linked_plan is not None:
        updates.append("linked_plan = %s")
        values.append(body.linked_plan.strip() or None)

    if not updates:
        raise HTTPException(status_code=400, detail="Nu ai trimis câmpuri pentru actualizare")

    values.extend([str(set_id), str(current_user.id)])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            UPDATE user_exercise_sets
            SET {", ".join(updates)}
            WHERE id = %s AND user_id = %s
            RETURNING id, name, linked_plan, filters, created_at
            """,
            values,
        )
        updated = cur.fetchone()
        if not updated:
            conn.rollback()
            raise HTTPException(status_code=404, detail="Set negăsit sau nu îți aparține")
        conn.commit()

    return {
        "id": str(updated["id"]),
        "name": updated["name"],
        "linked_plan": updated["linked_plan"],
        "filters": updated["filters"],
        "created_at": updated["created_at"].isoformat() if updated["created_at"] else None,
    }


@router.delete("/exercise-sets/{set_id}", tags=["ExerciseSets"])
def delete_exercise_set(set_id: uuid.UUID, current_user: UserDB = Depends(get_current_user), conn: Connection = Depends(get_db_conn)):
    with conn.cursor() as cur:
        cur.execute("SELECT exercise_id FROM user_exercise_set_items WHERE set_id = %s", (str(set_id),))
        exercise_ids = [str(row[0]) for row in cur.fetchall()]

        cur.execute(
            "DELETE FROM user_exercise_sets WHERE id = %s AND user_id = %s RETURNING id",
            (str(set_id), str(current_user.id)),
        )
        deleted = cur.fetchone()
        if not deleted:
            raise HTTPException(status_code=404, detail="Set negăsit sau nu îți aparține")

        if exercise_ids:
            placeholders = ",".join(["%s"] * len(exercise_ids))
            cur.execute(
                f"""
                DELETE FROM user_seen_exercises
                WHERE user_id = %s
                  AND exercise_id IN ({placeholders})
                  AND exercise_id NOT IN (
                      SELECT si.exercise_id FROM user_exercise_set_items si
                      JOIN user_exercise_sets s ON s.id = si.set_id
                      WHERE s.user_id = %s AND s.id != %s
                  )
                """,
                (str(current_user.id), *exercise_ids, str(current_user.id), str(set_id)),
            )

    conn.commit()
    return {"deleted": True}
