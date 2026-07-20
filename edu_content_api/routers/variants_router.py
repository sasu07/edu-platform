import hashlib
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from psycopg import Connection
from psycopg.rows import dict_row
from starlette.responses import HTMLResponse, StreamingResponse

from auth import (
    check_variant_gen_limit,
    get_current_user,
    require_pdf_premium,
    require_role,
)
from database import get_db_conn
from html_generator import get_html_generator
from models import SchoolTeacherUsage, UserDB, UserRole, VariantCreate, VariantDB, VariantUpdate
from pdf_generator import get_pdf_generator
from variant_generator import get_variant_generator

router = APIRouter()

STAFF_ROLES = (UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN)


def _ensure_variant_access(conn: Connection, variant_id, user: UserDB) -> None:
    """Autorizare la nivel de obiect: doar proprietarul variantei sau personalul.

    404 dacă varianta nu există, 403 dacă nu e a userului și userul nu e staff.
    Previne IDOR — un elev nu poate modifica/șterge varianta altui elev.
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT created_by_user_id_fk FROM variants WHERE id = %s", (variant_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
    if user.role in STAFF_ROLES:
        return
    owner = row["created_by_user_id_fk"]
    if owner is None or str(owner) != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nu ai acces la această variantă")


def save_variant_meta(conn: Connection, variant_id: str, user: UserDB, result: dict) -> None:
    if not variant_id:
        return
    try:
        exercise_ids: list[str] = []
        for subject in result.get("subjects", []):
            for exercise in subject.get("exercises", []):
                exercise_ids.append(str(exercise.get("id", exercise.get("exercise_id", ""))))
                for child in exercise.get("children", []):
                    exercise_ids.append(str(child.get("id", child.get("exercise_id", ""))))

        fingerprint = hashlib.sha256(",".join(sorted(exercise_ids)).encode()).hexdigest()[:32] if exercise_ids else None

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE variants
                SET created_by_user_id_fk = %s, fingerprint = %s
                WHERE id = %s
                """,
                (str(user.id), fingerprint, variant_id),
            )
        conn.commit()
    except Exception:
        pass


@router.post("/variants/", response_model=VariantDB, status_code=status.HTTP_201_CREATED)
def create_variant(variant: VariantCreate, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    query = """
    INSERT INTO variants (
        name, exam_type, profile, year, session, total_points,
        duration_minutes, instructions, status, created_by_user_id, created_by_user_id_fk
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id, name, exam_type, profile, year, session, total_points,
              duration_minutes, instructions, status, created_by_user_id,
              created_at, updated_at;
    """
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            exam_type_value = variant.exam_type.value if hasattr(variant.exam_type, "value") else variant.exam_type
            status_value = variant.status.value if hasattr(variant.status, "value") else variant.status

            cur.execute(
                query,
                (
                    variant.name,
                    exam_type_value,
                    variant.profile,
                    variant.year,
                    variant.session,
                    variant.total_points,
                    variant.duration_minutes,
                    variant.instructions,
                    status_value,
                    variant.created_by_user_id,
                    str(_user.id),  # owner autoritativ pentru verificările de acces
                ),
            )
            new_variant = cur.fetchone()
            conn.commit()
            return new_variant
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {exc}")


@router.get("/variants/", response_model=List[VariantDB])
def read_variants(
    exam_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    conn: Connection = Depends(get_db_conn),
    _user: UserDB = Depends(get_current_user),
):
    conditions = []
    params = []
    if exam_type:
        conditions.append("exam_type = %s")
        params.append(exam_type)
    if status_filter:
        conditions.append("status = %s")
        params.append(status_filter)
    # Non-staff văd doar variantele proprii (previne enumerarea tuturor variantelor)
    if _user.role not in STAFF_ROLES:
        conditions.append("created_by_user_id_fk = %s")
        params.append(str(_user.id))
    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    query = f"""
    SELECT id, name, exam_type, profile, year, session, total_points,
           duration_minutes, instructions, status, created_by_user_id,
           created_at, updated_at
    FROM variants{where_clause} ORDER BY created_at DESC;
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, tuple(params))
        return cur.fetchall()


@router.get("/variants/my", tags=["Variants"])
def my_variants_early(current_user: UserDB = Depends(get_current_user), conn: Connection = Depends(get_db_conn)):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, name, exam_type, profile, year, session,
                   total_points, duration_minutes, status, created_at, updated_at
            FROM variants
            WHERE created_by_user_id_fk = %s
            ORDER BY created_at DESC
            """,
            (str(current_user.id),),
        )
        return cur.fetchall()


@router.get("/variants/{variant_id}", response_model=VariantDB)
def read_variant(variant_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    _ensure_variant_access(conn, variant_id, _user)
    query = """
    SELECT id, name, exam_type, profile, year, session, total_points,
           duration_minutes, instructions, status, created_by_user_id,
           created_at, updated_at
    FROM variants WHERE id = %s;
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (variant_id,))
        variant = cur.fetchone()
        if variant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
        return variant


@router.put("/variants/{variant_id}", response_model=VariantDB)
def update_variant(variant_id: uuid.UUID, variant: VariantUpdate, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    _ensure_variant_access(conn, variant_id, _user)
    updates = []
    values = []
    update_data = variant.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    for key, value in update_data.items():
        updates.append(f"{key} = %s")
        if hasattr(value, "value"):
            value = value.value
        values.append(value)

    values.append(variant_id)
    query = f"""
    UPDATE variants SET {', '.join(updates)}
    WHERE id = %s
    RETURNING id, name, exam_type, profile, year, session, total_points,
              duration_minutes, instructions, status, created_by_user_id,
              created_at, updated_at;
    """
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, values)
            updated_variant = cur.fetchone()
            conn.commit()
            if updated_variant is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
            return updated_variant
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {exc}")


@router.delete("/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variant(variant_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    _ensure_variant_access(conn, variant_id, _user)
    query = "DELETE FROM variants WHERE id = %s RETURNING id;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (variant_id,))
            deleted_count = cur.rowcount
            conn.commit()
            if deleted_count == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {exc}")


@router.post("/variants/{variant_id}/exercises/")
def add_exercises_to_variant(variant_id: uuid.UUID, exercise_ids: List[uuid.UUID], conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    _ensure_variant_access(conn, variant_id, _user)
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT COALESCE(MAX(order_index), -1) as max_order FROM variant_exercises WHERE variant_id = %s",
                (variant_id,),
            )
            result = cur.fetchone()
            current_max = result["max_order"] if result else -1

        query = """
        INSERT INTO variant_exercises (variant_id, exercise_id, order_index)
        VALUES (%s, %s, %s)
        ON CONFLICT (variant_id, exercise_id) DO NOTHING
        RETURNING id;
        """
        added_count = 0
        with conn.cursor(row_factory=dict_row) as cur:
            for idx, exercise_id in enumerate(exercise_ids):
                cur.execute(query, (variant_id, exercise_id, current_max + idx + 1))
                if cur.fetchone():
                    added_count += 1

        conn.commit()
        return {"status": "success", "added_count": added_count}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")


@router.get("/variants/{variant_id}/exercises/")
def get_variant_exercises(variant_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    _ensure_variant_access(conn, variant_id, _user)
    query = """
    SELECT
        ve.id, ve.variant_id, ve.exercise_id, ve.order_index, ve.section_name,
        e.statement_latex, e.statement_text, e.points, e.item_type, e.subject_part,
        e.difficulty, e.exam_type
    FROM variant_exercises ve
    JOIN exercises e ON ve.exercise_id = e.id
    WHERE ve.variant_id = %s
    ORDER BY ve.order_index;
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, (variant_id,))
        return cur.fetchall()


@router.delete("/variants/{variant_id}/exercises/{exercise_id}")
def remove_exercise_from_variant(variant_id: uuid.UUID, exercise_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    _ensure_variant_access(conn, variant_id, _user)
    query = "DELETE FROM variant_exercises WHERE variant_id = %s AND exercise_id = %s RETURNING id;"
    try:
        with conn.cursor() as cur:
            cur.execute(query, (variant_id, exercise_id))
            deleted_count = cur.rowcount
            conn.commit()
            if deleted_count == 0:
                raise HTTPException(status_code=404, detail="Exercise not found in variant")
            return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")


@router.put("/variants/{variant_id}/exercises/reorder")
def reorder_variant_exercises(variant_id: uuid.UUID, exercise_order: List[uuid.UUID], conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    _ensure_variant_access(conn, variant_id, _user)
    query = """
    UPDATE variant_exercises
    SET order_index = %s
    WHERE variant_id = %s AND exercise_id = %s;
    """
    try:
        with conn.cursor() as cur:
            for idx, exercise_id in enumerate(exercise_order):
                cur.execute(query, (idx, variant_id, exercise_id))
        conn.commit()
        return {"status": "success", "reordered_count": len(exercise_order)}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")


@router.get("/variants/{variant_id}/download-pdf")
def download_variant_pdf(
    variant_id: uuid.UUID,
    current_user: UserDB = Depends(require_pdf_premium),
    conn: Connection = Depends(get_db_conn),
):
    _ensure_variant_access(conn, variant_id, current_user)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, name FROM variants WHERE id = %s;", (variant_id,))
        variant = cur.fetchone()
    if not variant:
        raise HTTPException(status_code=404, detail="Varianta nu a fost găsită")

    try:
        pdf_buffer = get_pdf_generator(conn).generate_variant_pdf(variant_id)
        safe_name = variant["name"].replace(" ", "_").replace("/", "-")
        filename = f"{safe_name}.pdf"
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Eroare la generarea PDF-ului: {str(exc)}")


def _ensure_variant_exists(conn: Connection, variant_id: uuid.UUID) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM variants WHERE id = %s;", (variant_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Varianta nu a fost găsită")


@router.get("/variants/{variant_id}/preview-exam", response_class=HTMLResponse)
def preview_variant_exam(variant_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    _ensure_variant_access(conn, variant_id, _user)
    try:
        return HTMLResponse(content=get_html_generator(conn).generate(variant_id, mode="exam"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Eroare: {str(exc)}")


@router.get("/variants/{variant_id}/preview-solutions", response_class=HTMLResponse)
def preview_variant_solutions(variant_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    _ensure_variant_access(conn, variant_id, _user)
    try:
        return HTMLResponse(content=get_html_generator(conn).generate(variant_id, mode="solutions"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Eroare: {str(exc)}")


@router.get("/variants/{variant_id}/preview-barem", response_class=HTMLResponse)
def preview_variant_barem(variant_id: uuid.UUID, conn: Connection = Depends(get_db_conn), _user: UserDB = Depends(get_current_user)):
    _ensure_variant_access(conn, variant_id, _user)
    try:
        return HTMLResponse(content=get_html_generator(conn).generate(variant_id, mode="barem"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Eroare: {str(exc)}")


@router.post("/variants/generate")
async def generate_variant_auto(
    request: Request,
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    if current_user.role in (UserRole.SCHOOL_TEACHER, UserRole.STUDENT):
        check_variant_gen_limit(str(current_user.id), conn)

    try:
        generator = get_variant_generator(conn)
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type:
            body = await request.json()
            variant_id = body.get("variant_id")
            if not variant_id:
                raise HTTPException(status_code=400, detail="Lipsește variant_id din body")

            difficulty_range = None
            if body.get("difficulty_min") is not None and body.get("difficulty_max") is not None:
                difficulty_range = (body["difficulty_min"], body["difficulty_max"])

            result = generator.generate_for_existing_variant(
                variant_id=uuid.UUID(variant_id),
                difficulty_range=difficulty_range,
            )
            save_variant_meta(conn, variant_id, current_user, result)
            return {"status": "success", "message": f"Exerciții generate pentru varianta: {result['name']}", **result}

        form = await request.form()
        name = form.get("name")
        exam_type = form.get("exam_type")
        if not name or not exam_type:
            raise HTTPException(status_code=400, detail="Câmpurile 'name' și 'exam_type' sunt obligatorii")

        profile = form.get("profile") or None
        year_str = form.get("year")
        year = int(year_str) if year_str else None
        session = form.get("session") or None
        diff_min_str = form.get("difficulty_min")
        diff_max_str = form.get("difficulty_max")
        dur_str = form.get("duration_minutes", "180")

        difficulty_range = None
        if diff_min_str and diff_max_str:
            difficulty_range = (int(diff_min_str), int(diff_max_str))

        result = generator.generate_variant(
            name=str(name),
            exam_type=str(exam_type),
            profile=str(profile) if profile else None,
            year=year,
            session=str(session) if session else None,
            difficulty_range=difficulty_range,
            duration_minutes=int(dur_str),
        )
        save_variant_meta(conn, str(result.get("variant_id", "")), current_user, result)
        return {"status": "success", "message": f"Variantă generată automat: {name}", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error generating variant: {exc}")


@router.get("/school-teacher/usage", response_model=SchoolTeacherUsage, tags=["School Teacher"])
def school_teacher_usage(
    current_user: UserDB = Depends(require_role(UserRole.SCHOOL_TEACHER, UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT COUNT(*) as cnt FROM variants
            WHERE created_by_user_id_fk = %s
              AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
            """,
            (str(current_user.id),),
        )
        row = cur.fetchone()

    used = row["cnt"] if row else 0
    limit = None
    if current_user.role == UserRole.SCHOOL_TEACHER:
        limit = 1

    return SchoolTeacherUsage(used_this_month=used, monthly_limit=limit)

