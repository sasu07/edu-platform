from datetime import date, timedelta
import secrets
import string

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from psycopg import Connection
from psycopg.rows import dict_row

from auth import get_current_user, hash_password
from database import get_db_conn
from email_service import send_parent_invite, send_parent_linked
from models import (
    AdminParentStudentLinkRequest,
    ParentLinkRequest,
    ParentStudentDB,
    ParentStudentStats,
    StudentActivityDay,
    UserRole,
)

router = APIRouter()


@router.post("/parent/link-student", response_model=ParentStudentDB, tags=["Parent"])
def link_parent_to_student(
    body: ParentLinkRequest,
    background_tasks: BackgroundTasks,
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    if current_user.role not in (UserRole.STUDENT, UserRole.SCHOOL_TEACHER):
        raise HTTPException(status_code=403, detail="Doar elevii pot adăuga un părinte")

    parent_email = body.parent_email.strip().lower()

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT ps.id, ps.parent_id, ps.student_id, ps.linked_at,
                      p.email as parent_email, p.full_name as parent_name,
                      s.full_name as student_name
               FROM parent_student ps
               JOIN users p ON p.id = ps.parent_id
               JOIN users s ON s.id = ps.student_id
               WHERE ps.student_id=%s AND p.email=%s""",
            (str(current_user.id), parent_email),
        )
        existing = cur.fetchone()
        if existing:
            return ParentStudentDB(**existing)

        cur.execute("SELECT id, full_name, email, role FROM users WHERE email=%s", (parent_email,))
        parent_user = cur.fetchone()
        created_new = False

        if not parent_user:
            alphabet = string.ascii_letters + string.digits
            temp_password = "".join(secrets.choice(alphabet) for _ in range(10))
            parent_name = body.parent_name or parent_email.split("@")[0]
            cur.execute(
                """INSERT INTO users (email, password_hash, full_name, role)
                   VALUES (%s, %s, %s, 'parent') RETURNING id, full_name, email""",
                (parent_email, hash_password(temp_password), parent_name),
            )
            parent_user = cur.fetchone()
            created_new = True
        elif parent_user.get("role") not in (None, "parent"):
            raise HTTPException(status_code=400, detail="Emailul aparține unui alt tip de cont")

        cur.execute(
            """INSERT INTO parent_student (parent_id, student_id)
               VALUES (%s, %s) RETURNING id, linked_at""",
            (str(parent_user["id"]), str(current_user.id)),
        )
        link_row = cur.fetchone()
        conn.commit()

        result = ParentStudentDB(
            id=link_row["id"],
            parent_id=parent_user["id"],
            student_id=current_user.id,
            parent_email=parent_email,
            parent_name=parent_user["full_name"],
            student_name=current_user.full_name,
            linked_at=link_row["linked_at"],
        )

    if created_new:
        background_tasks.add_task(
            send_parent_invite,
            parent_email,
            parent_user["full_name"],
            current_user.full_name,
            temp_password,
        )
    else:
        background_tasks.add_task(
            send_parent_linked,
            parent_email,
            parent_user["full_name"],
            current_user.full_name,
        )

    return result


@router.get("/student/my-parents", response_model=list[ParentStudentDB], tags=["Parent"])
def get_my_parents(conn: Connection = Depends(get_db_conn), current_user=Depends(get_current_user)):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT ps.id, ps.parent_id, ps.student_id, ps.linked_at,
                      p.email as parent_email, p.full_name as parent_name,
                      s.full_name as student_name
               FROM parent_student ps
               JOIN users p ON p.id = ps.parent_id
               JOIN users s ON s.id = ps.student_id
               WHERE ps.student_id=%s ORDER BY ps.linked_at DESC""",
            (str(current_user.id),),
        )
        rows = cur.fetchall()
    return [ParentStudentDB(**row) for row in rows]


@router.delete("/student/my-parents/{parent_id}", tags=["Parent"])
def remove_parent_link(parent_id: str, conn: Connection = Depends(get_db_conn), current_user=Depends(get_current_user)):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM parent_student WHERE student_id=%s AND parent_id=%s", (str(current_user.id), parent_id))
        conn.commit()
    return {"ok": True}


@router.get("/parent/students", response_model=list[ParentStudentDB], tags=["Parent"])
def get_my_students(conn: Connection = Depends(get_db_conn), current_user=Depends(get_current_user)):
    if current_user.role != UserRole.PARENT:
        raise HTTPException(status_code=403, detail="Doar părinții pot accesa această resursă")
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT ps.id, ps.parent_id, ps.student_id, ps.linked_at,
                      p.email as parent_email, p.full_name as parent_name,
                      s.full_name as student_name
               FROM parent_student ps
               JOIN users p ON p.id = ps.parent_id
               JOIN users s ON s.id = ps.student_id
               WHERE ps.parent_id=%s ORDER BY ps.linked_at DESC""",
            (str(current_user.id),),
        )
        rows = cur.fetchall()
    return [ParentStudentDB(**row) for row in rows]


@router.get("/parent/students/{student_id}/stats", response_model=ParentStudentStats, tags=["Parent"])
def get_student_stats(student_id: str, conn: Connection = Depends(get_db_conn), current_user=Depends(get_current_user)):
    if current_user.role == UserRole.PARENT:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM parent_student WHERE parent_id=%s AND student_id=%s", (str(current_user.id), student_id))
            if not cur.fetchone():
                raise HTTPException(status_code=403, detail="Nu ești legat de acest elev")
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Acces interzis")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT full_name, email FROM users WHERE id=%s", (student_id,))
        student = cur.fetchone()
        if not student:
            raise HTTPException(status_code=404, detail="Elevul nu există")

        cur.execute("SELECT COUNT(*) as cnt FROM student_progress WHERE student_id=%s", (student_id,))
        total_seen = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) as cnt FROM student_progress WHERE student_id=%s AND completed=TRUE", (student_id,))
        total_completed = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) as cnt FROM variants WHERE created_by_user_id=%s", (student_id,))
        total_variants = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) as cnt FROM help_requests WHERE student_id=%s", (student_id,))
        total_flags = cur.fetchone()["cnt"]

        cur.execute("SELECT MAX(last_seen_at) as last_active FROM student_progress WHERE student_id=%s", (student_id,))
        last_active_row = cur.fetchone()
        last_active = last_active_row["last_active"].isoformat() if last_active_row and last_active_row["last_active"] else None

        cur.execute(
            """
            SELECT
                DATE(last_seen_at) as day,
                COUNT(*) as exercises_seen,
                SUM(CASE WHEN completed THEN 1 ELSE 0 END) as exercises_completed
            FROM student_progress
            WHERE student_id=%s AND last_seen_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(last_seen_at)
            ORDER BY day
            """,
            (student_id,),
        )
        seen_by_day = {str(row["day"]): row for row in cur.fetchall()}

        cur.execute(
            """
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM variants WHERE created_by_user_id=%s AND created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            """,
            (student_id,),
        )
        variants_by_day = {str(row["day"]): row["cnt"] for row in cur.fetchall()}

        cur.execute(
            """
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM help_requests WHERE student_id=%s AND created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(created_at)
            """,
            (student_id,),
        )
        flags_by_day = {str(row["day"]): row["cnt"] for row in cur.fetchall()}

        cur.execute(
            """
            SELECT e.metadata->>'subiect' as subiect, COUNT(*) as cnt
            FROM student_progress sp
            JOIN exercises e ON e.id = sp.exercise_id
            WHERE sp.student_id=%s AND sp.completed=TRUE AND e.metadata IS NOT NULL
            GROUP BY e.metadata->>'subiect'
            """,
            (student_id,),
        )
        completion_by_subiect = {str(row["subiect"]): row["cnt"] for row in cur.fetchall() if row["subiect"]}

    all_days = []
    today = date.today()
    for index in range(29, -1, -1):
        day = str(today - timedelta(days=index))
        seen_day = seen_by_day.get(day, {})
        all_days.append(
            StudentActivityDay(
                date=day,
                exercises_seen=seen_day.get("exercises_seen", 0),
                exercises_completed=seen_day.get("exercises_completed", 0),
                variants_generated=variants_by_day.get(day, 0),
                flags_sent=flags_by_day.get(day, 0),
            )
        )

    return ParentStudentStats(
        student_id=student_id,
        student_name=student["full_name"],
        student_email=student["email"],
        total_exercises_seen=total_seen,
        total_exercises_completed=total_completed,
        total_variants_generated=total_variants,
        total_flags_sent=total_flags,
        last_active_at=last_active,
        activity_last_30_days=all_days,
        completion_by_subiect=completion_by_subiect,
    )


@router.post("/admin/parent-student", response_model=ParentStudentDB, tags=["Admin"])
def admin_link_parent_student(
    body: AdminParentStudentLinkRequest,
    background_tasks: BackgroundTasks,
    conn: Connection = Depends(get_db_conn),
    current_user=Depends(get_current_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Doar admin")

    parent_id = body.parent_id
    student_id = body.student_id

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, full_name, email, role FROM users WHERE id=%s", (parent_id,))
        parent = cur.fetchone()
        cur.execute("SELECT id, full_name, email FROM users WHERE id=%s", (student_id,))
        student = cur.fetchone()
        if not parent or not student:
            raise HTTPException(status_code=404, detail="Utilizator inexistent")

        cur.execute(
            """INSERT INTO parent_student (parent_id, student_id)
               VALUES (%s, %s)
               ON CONFLICT (parent_id, student_id) DO NOTHING
               RETURNING id, linked_at""",
            (parent_id, student_id),
        )
        row = cur.fetchone()
        conn.commit()

    if row:
        background_tasks.add_task(send_parent_linked, parent["email"], parent["full_name"], student["full_name"])
        return ParentStudentDB(
            id=row["id"],
            parent_id=parent_id,
            student_id=student_id,
            parent_email=parent["email"],
            parent_name=parent["full_name"],
            student_name=student["full_name"],
            linked_at=row["linked_at"],
        )
    raise HTTPException(status_code=409, detail="Legătura există deja")


@router.get("/admin/parent-students", tags=["Admin"])
def admin_get_parent_students(conn: Connection = Depends(get_db_conn), current_user=Depends(get_current_user)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Doar admin")
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT ps.id, ps.parent_id, ps.student_id, ps.linked_at,
                      p.email as parent_email, p.full_name as parent_name,
                      s.full_name as student_name, s.email as student_email
               FROM parent_student ps
               JOIN users p ON p.id = ps.parent_id
               JOIN users s ON s.id = ps.student_id
               ORDER BY ps.linked_at DESC"""
        )
        return cur.fetchall()


@router.delete("/admin/parent-student/{link_id}", tags=["Admin"])
def admin_remove_parent_student(link_id: str, conn: Connection = Depends(get_db_conn), current_user=Depends(get_current_user)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Doar admin")
    with conn.cursor() as cur:
        cur.execute("DELETE FROM parent_student WHERE id=%s", (link_id,))
        conn.commit()
    return {"ok": True}
