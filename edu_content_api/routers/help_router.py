import os
import shutil
import uuid
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from psycopg import Connection
from psycopg.rows import dict_row

from auth import get_current_user, require_premium, require_role
from bootstrap import UPLOAD_DIR
from database import get_db_conn
from email_service import send_new_request_to_teacher, send_response_to_student
from models import (
    HelpFlagType,
    HelpRequestCreate,
    HelpRequestDB,
    HelpRequestStatus,
    HelpResponseCreate,
    HelpResponseDB,
    UserDB,
    UserRole,
)

router = APIRouter()


@router.get("/help-requests/my-full", tags=["Help"])
def my_help_requests_full(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                hr.id,
                hr.flag_type,
                hr.status,
                hr.notes,
                hr.created_at,
                hr.updated_at,
                e.statement_latex,
                e.difficulty,
                e.points,
                e.metadata->>'path' AS exercise_path,
                hr.exercise_id,
                hrsp.content_text,
                hrsp.video_path,
                hrsp.zoom_link,
                hrsp.scheduled_at,
                hrsp.created_at AS responded_at,
                u.full_name AS teacher_name
            FROM help_requests hr
            JOIN exercises e ON e.id = hr.exercise_id
            LEFT JOIN help_responses hrsp ON hrsp.request_id = hr.id
            LEFT JOIN users u ON u.id = hrsp.teacher_id
            WHERE hr.student_id = %s
            ORDER BY hr.created_at DESC
            """,
            (str(current_user.id),),
        )
        return cur.fetchall()


@router.post("/help-requests/", response_model=HelpRequestDB, tags=["Help"])
def create_help_request(
    body: HelpRequestCreate,
    background_tasks: BackgroundTasks,
    current_user: UserDB = Depends(require_premium),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM exercises WHERE id = %s", (str(body.exercise_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Exercițiu negăsit")

        cur.execute(
            """
            INSERT INTO help_requests (student_id, exercise_id, flag_type, notes)
            VALUES (%s, %s, %s, %s)
            RETURNING id, student_id, exercise_id, flag_type, status, notes,
                      assigned_teacher_id, created_at, updated_at
            """,
            (str(current_user.id), str(body.exercise_id), body.flag_type.value, body.notes),
        )
        row = cur.fetchone()
        request_id = str(row["id"])

        flag_labels = {"WRITTEN": "Rezolvare scrisă", "VIDEO": "Rezolvare video", "LIVE": "Sesiune live"}
        flag_label = flag_labels.get(body.flag_type.value, body.flag_type.value)

        cur.execute("SELECT id, full_name, email FROM users WHERE role = 'teacher' AND is_active = TRUE")
        teachers = cur.fetchall()
        for teacher in teachers:
            cur.execute(
                """
                INSERT INTO notifications (user_id, type, title, body, related_id)
                VALUES (%s, 'new_request', %s, %s, %s)
                """,
                (
                    str(teacher["id"]),
                    f"Cerere nouă: {flag_label}",
                    f"{current_user.full_name} a solicitat ajutor pentru un exercițiu.",
                    request_id,
                ),
            )
            background_tasks.add_task(
                send_new_request_to_teacher,
                teacher["email"],
                teacher["full_name"],
                current_user.full_name,
                body.flag_type.value,
                request_id,
            )

        conn.commit()
    return HelpRequestDB(**row)


@router.get("/help-requests/my", response_model=List[HelpRequestDB], tags=["Help"])
def my_help_requests(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, student_id, exercise_id, flag_type, status, notes,
                   assigned_teacher_id, created_at, updated_at
            FROM help_requests WHERE student_id = %s ORDER BY created_at DESC
            """,
            (str(current_user.id),),
        )
        return [HelpRequestDB(**row) for row in cur.fetchall()]


@router.get("/help-requests/pending", response_model=List[dict], tags=["Help"])
def pending_help_requests(
    _teacher: UserDB = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                hr.id, hr.flag_type, hr.status, hr.notes, hr.created_at, hr.updated_at,
                hr.assigned_teacher_id,
                u.full_name AS student_name, u.email AS student_email,
                e.statement_latex, e.difficulty, e.points,
                e.metadata->>'path' AS exercise_path,
                hr.exercise_id, hr.student_id
            FROM help_requests hr
            JOIN users u ON u.id = hr.student_id
            JOIN exercises e ON e.id = hr.exercise_id
            WHERE hr.status IN ('pending', 'assigned')
            ORDER BY hr.created_at ASC
            """
        )
        return cur.fetchall()


@router.put("/help-requests/{request_id}/assign", response_model=HelpRequestDB, tags=["Help"])
def assign_help_request(
    request_id: uuid.UUID,
    current_user: UserDB = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, status, assigned_teacher_id FROM help_requests WHERE id = %s",
            (str(request_id),),
        )
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Request negăsit")
        if existing["status"] == HelpRequestStatus.RESOLVED.value:
            raise HTTPException(status_code=409, detail="Request-ul este deja rezolvat")
        if existing["assigned_teacher_id"] and str(existing["assigned_teacher_id"]) != str(current_user.id):
            raise HTTPException(status_code=409, detail="Request-ul este deja preluat de alt profesor")

        cur.execute(
            """
            UPDATE help_requests
            SET status = 'assigned', assigned_teacher_id = %s, updated_at = NOW()
            WHERE id = %s
            RETURNING id, student_id, exercise_id, flag_type, status, notes,
                      assigned_teacher_id, created_at, updated_at
            """,
            (str(current_user.id), str(request_id)),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Request negăsit")
        conn.commit()
    return HelpRequestDB(**row)


@router.post("/help-requests/{request_id}/respond", response_model=HelpResponseDB, tags=["Help"])
def respond_to_help_request(
    request_id: uuid.UUID,
    body: HelpResponseCreate,
    background_tasks: BackgroundTasks,
    current_user: UserDB = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, flag_type, status, assigned_teacher_id FROM help_requests WHERE id = %s",
            (str(request_id),),
        )
        request_row = cur.fetchone()
        if not request_row:
            raise HTTPException(status_code=404, detail="Request negăsit")
        if request_row["status"] == HelpRequestStatus.RESOLVED.value:
            raise HTTPException(status_code=409, detail="Request-ul este deja rezolvat")

        assigned_teacher_id = request_row["assigned_teacher_id"]
        if assigned_teacher_id and str(assigned_teacher_id) != str(current_user.id) and current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Request-ul este asignat altui profesor")
        if not assigned_teacher_id:
            cur.execute(
                """
                UPDATE help_requests
                SET status = 'assigned', assigned_teacher_id = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (str(current_user.id), str(request_id)),
            )

        cur.execute(
            """
            INSERT INTO help_responses (request_id, teacher_id, content_text, zoom_link, scheduled_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, request_id, teacher_id, content_text, video_path, zoom_link, scheduled_at, created_at
            """,
            (str(request_id), str(current_user.id), body.content_text, body.zoom_link, body.scheduled_at),
        )
        response_row = cur.fetchone()

        cur.execute(
            "UPDATE help_requests SET status = 'resolved', updated_at = NOW() WHERE id = %s",
            (str(request_id),),
        )

        cur.execute(
            "SELECT hr.student_id, u.email, u.full_name FROM help_requests hr JOIN users u ON u.id = hr.student_id WHERE hr.id = %s",
            (str(request_id),),
        )
        student = cur.fetchone()

        flag_labels = {"WRITTEN": "Rezolvare scrisă", "VIDEO": "Rezolvare video", "LIVE": "Sesiune live"}
        flag_label = flag_labels.get(request_row["flag_type"], request_row["flag_type"])

        if student:
            cur.execute(
                """
                INSERT INTO notifications (user_id, type, title, body, related_id)
                VALUES (%s, 'help_response', %s, %s, %s)
                """,
                (
                    str(student["student_id"]),
                    f"Ai primit un răspuns: {flag_label}",
                    f"Profesorul {current_user.full_name} a răspuns la cererea ta.",
                    str(request_id),
                ),
            )
            background_tasks.add_task(
                send_response_to_student,
                student["email"],
                student["full_name"],
                current_user.full_name,
                request_row["flag_type"],
            )

        conn.commit()
    return HelpResponseDB(**response_row)


@router.post("/help-requests/{request_id}/upload-video", tags=["Help"])
def upload_help_video(
    request_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: UserDB = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, flag_type FROM help_requests WHERE id = %s",
            (str(request_id),),
        )
        request_row = cur.fetchone()
        if not request_row:
            raise HTTPException(status_code=404, detail="Request negăsit")
        if request_row["flag_type"] != HelpFlagType.VIDEO.value:
            raise HTTPException(status_code=400, detail="Acest request nu este de tip VIDEO")

    video_dir = os.path.join(UPLOAD_DIR, "help_videos")
    os.makedirs(video_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    filename = f"{request_id}{ext}"
    file_path = os.path.join(video_dir, filename)
    video_url = f"/uploads/help_videos/{filename}"

    with open(file_path, "wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO help_responses (request_id, teacher_id, video_path)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (str(request_id), str(current_user.id), video_url),
        )
        cur.execute(
            "UPDATE help_requests SET status = 'resolved', updated_at = NOW() WHERE id = %s",
            (str(request_id),),
        )
        conn.commit()

    return {"status": "ok", "video_path": video_url}


@router.get("/help-requests/{request_id}/response", response_model=HelpResponseDB, tags=["Help"])
def get_help_response(
    request_id: uuid.UUID,
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT student_id FROM help_requests WHERE id = %s",
            (str(request_id),),
        )
        request_row = cur.fetchone()
        if not request_row:
            raise HTTPException(status_code=404, detail="Request negăsit")
        if current_user.role == UserRole.STUDENT and str(request_row["student_id"]) != str(current_user.id):
            raise HTTPException(status_code=403, detail="Acces interzis")

        cur.execute(
            """
            SELECT id, request_id, teacher_id, content_text, video_path, zoom_link, scheduled_at, created_at
            FROM help_responses WHERE request_id = %s ORDER BY created_at DESC LIMIT 1
            """,
            (str(request_id),),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Niciun răspuns încă")
    return HelpResponseDB(**row)
