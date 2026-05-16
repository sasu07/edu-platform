import json
import secrets
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from psycopg.rows import dict_row

from auth import get_current_user
from database import get_db_conn
from models import (
    ClassGroupCreateRequest,
    ClassGroupJoinRequest,
    ClassMembershipUpdateRequest,
    UserDB,
    UserRole,
    WeeklyChallengeCreateRequest,
)

router = APIRouter()


def _week_bounds(week_start: Optional[str] = None) -> tuple[date, date]:
    if week_start:
        start = datetime.fromisoformat(week_start).date()
    else:
        today = datetime.now().date()
        start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


def _normalize_subiect(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().upper()
    mapping = {"S1": "1", "S2": "2", "S3": "3", "1": "1", "2": "2", "3": "3"}
    return mapping.get(normalized)


def _display_name(row: dict, viewer_user_id: str, is_teacher_view: bool) -> str:
    if row["student_id"] == viewer_user_id:
        return "Tu"
    if row.get("is_anonymous") and row.get("pseudonym") and not is_teacher_view:
        return row["pseudonym"]
    return row["full_name"]


def _generate_class_code(conn: Connection) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    with conn.cursor() as cur:
        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(6))
            cur.execute("SELECT 1 FROM class_groups WHERE class_code=%s", (code,))
            if not cur.fetchone():
                return code


def _ensure_teacher_owns_class(conn: Connection, class_id: str, teacher_id: str) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM class_groups WHERE id=%s AND teacher_id=%s", (class_id, teacher_id))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Clasa nu există sau nu îți aparține")
    return dict(row)


def _ensure_student_membership(conn: Connection, class_id: str, student_id: str) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT m.*, c.name as class_name, c.allow_anonymous, c.teacher_id
               FROM class_group_memberships m
               JOIN class_groups c ON c.id = m.class_id
               WHERE m.class_id=%s AND m.student_id=%s AND m.is_active=TRUE""",
            (class_id, student_id),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=403, detail="Nu faci parte din această clasă")
    return dict(row)


def _build_leaderboard(
    conn: Connection,
    class_id: str,
    viewer_user_id: str,
    week_start: date,
    week_end: date,
    is_teacher_view: bool,
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                m.student_id,
                u.full_name,
                m.pseudonym,
                m.is_anonymous,
                COALESCE(SUM(x.xp_gained), 0) AS xp_week
            FROM class_group_memberships m
            JOIN users u ON u.id = m.student_id
            LEFT JOIN xp_log x
                ON x.user_id = m.student_id
               AND DATE(x.created_at) BETWEEN %s AND %s
            WHERE m.class_id=%s AND m.is_active=TRUE
            GROUP BY m.student_id, u.full_name, m.pseudonym, m.is_anonymous
            ORDER BY xp_week DESC, u.full_name
            """,
            (week_start, week_end, class_id),
        )
        rows = cur.fetchall()

    leaderboard = []
    for index, row in enumerate(rows, start=1):
        leaderboard.append(
            {
                "student_id": str(row["student_id"]),
                "display_name": _display_name(row, viewer_user_id, is_teacher_view),
                "xp_week": int(row["xp_week"] or 0),
                "rank": index,
                "is_you": str(row["student_id"]) == viewer_user_id,
                "is_anonymous": bool(row["is_anonymous"]),
            }
        )
    return leaderboard


def _build_challenges(
    conn: Connection,
    class_id: str,
    viewer_user_id: str,
    week_start: date,
    week_end: date,
    is_teacher_view: bool,
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, title, description, target_count, filters, week_start, week_end, created_at
            FROM weekly_class_challenges
            WHERE class_id=%s AND week_start=%s
            ORDER BY created_at DESC
            """,
            (class_id, week_start),
        )
        challenges = cur.fetchall()

    results = []
    for challenge in challenges:
        filters = challenge["filters"] or {}
        subiect = _normalize_subiect(filters.get("subiect_tag"))
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    m.student_id,
                    u.full_name,
                    m.pseudonym,
                    m.is_anonymous,
                    COUNT(e.id) AS progress_count
                FROM class_group_memberships m
                JOIN users u ON u.id = m.student_id
                LEFT JOIN student_progress sp
                    ON sp.student_id = m.student_id
                   AND sp.completed = TRUE
                   AND DATE(sp.completed_at) BETWEEN %s AND %s
                LEFT JOIN exercises e
                    ON e.id = sp.exercise_id
                   AND (%s::text IS NULL OR e.metadata->>'subiect' = %s::text)
                WHERE m.class_id=%s AND m.is_active=TRUE
                GROUP BY m.student_id, u.full_name, m.pseudonym, m.is_anonymous
                ORDER BY progress_count DESC, u.full_name
                """,
                (challenge["week_start"], challenge["week_end"], subiect, subiect, class_id),
            )
            progress_rows = cur.fetchall()

        participant_progress = []
        for row in progress_rows:
            progress_count = int(row["progress_count"] or 0)
            participant_progress.append(
                {
                    "student_id": str(row["student_id"]),
                    "display_name": _display_name(row, viewer_user_id, is_teacher_view),
                    "progress_count": progress_count,
                    "completed": progress_count >= int(challenge["target_count"]),
                    "is_you": str(row["student_id"]) == viewer_user_id,
                }
            )

        results.append(
            {
                "id": str(challenge["id"]),
                "title": challenge["title"],
                "description": challenge["description"],
                "target_count": int(challenge["target_count"]),
                "filters": filters,
                "week_start": str(challenge["week_start"]),
                "week_end": str(challenge["week_end"]),
                "participant_progress": participant_progress,
            }
        )
    return results


@router.post("/teacher/classes", tags=["League"])
def create_class_group(
    body: ClassGroupCreateRequest,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role not in (UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Doar profesorii pot crea clase")

    code = _generate_class_code(conn)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO class_groups (teacher_id, name, class_code, allow_anonymous)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (str(current_user.id), body.name.strip(), code, body.allow_anonymous),
        )
        row = cur.fetchone()
        conn.commit()
    return dict(row)


@router.get("/teacher/classes", tags=["League"])
def list_teacher_classes(
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role not in (UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")

    with conn.cursor(row_factory=dict_row) as cur:
        if current_user.role == UserRole.ADMIN:
            cur.execute(
                """
                SELECT c.*, u.full_name AS teacher_name,
                       COUNT(m.id) FILTER (WHERE m.is_active=TRUE) AS member_count
                FROM class_groups c
                JOIN users u ON u.id = c.teacher_id
                LEFT JOIN class_group_memberships m ON m.class_id = c.id
                GROUP BY c.id, u.full_name
                ORDER BY c.created_at DESC
                """
            )
        else:
            cur.execute(
                """
                SELECT c.*, u.full_name AS teacher_name,
                       COUNT(m.id) FILTER (WHERE m.is_active=TRUE) AS member_count
                FROM class_groups c
                JOIN users u ON u.id = c.teacher_id
                LEFT JOIN class_group_memberships m ON m.class_id = c.id
                WHERE c.teacher_id=%s
                GROUP BY c.id, u.full_name
                ORDER BY c.created_at DESC
                """,
                (str(current_user.id),),
            )
        return [dict(row) for row in cur.fetchall()]


@router.post("/teacher/classes/{class_id}/challenges", tags=["League"])
def create_weekly_class_challenge(
    class_id: str,
    body: WeeklyChallengeCreateRequest,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role not in (UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")

    if current_user.role != UserRole.ADMIN:
        _ensure_teacher_owns_class(conn, class_id, str(current_user.id))

    week_start, week_end = _week_bounds()
    filters = {}
    subiect = _normalize_subiect(body.subiect_tag)
    if subiect:
        filters["subiect_tag"] = subiect

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO weekly_class_challenges
            (class_id, title, description, target_count, filters, week_start, week_end, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                class_id,
                body.title.strip(),
                body.description.strip() if body.description else None,
                body.target_count,
                json.dumps(filters),
                week_start,
                week_end,
                str(current_user.id),
            ),
        )
        row = cur.fetchone()
        conn.commit()
    return dict(row)


@router.post("/student/classes/join", tags=["League"])
def join_class_group(
    body: ClassGroupJoinRequest,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Doar elevii se pot alătura unei clase")

    class_code = body.class_code.strip().upper()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM class_groups WHERE class_code=%s", (class_code,))
        class_row = cur.fetchone()
        if not class_row:
            raise HTTPException(status_code=404, detail="Cod de clasă invalid")

        cur.execute(
            """
            INSERT INTO class_group_memberships (class_id, student_id, pseudonym, is_anonymous)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (class_id, student_id) DO UPDATE
            SET is_active=TRUE,
                pseudonym=EXCLUDED.pseudonym,
                is_anonymous=EXCLUDED.is_anonymous
            RETURNING *
            """,
            (
                str(class_row["id"]),
                str(current_user.id),
                (body.pseudonym or "").strip() or None,
                bool(body.is_anonymous and class_row["allow_anonymous"]),
            ),
        )
        membership = cur.fetchone()
        conn.commit()

    return {
        "class": dict(class_row),
        "membership": dict(membership),
    }


@router.put("/student/classes/{class_id}/membership", tags=["League"])
def update_class_membership(
    class_id: str,
    body: ClassMembershipUpdateRequest,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Acces interzis")

    membership = _ensure_student_membership(conn, class_id, str(current_user.id))
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            UPDATE class_group_memberships
            SET pseudonym=%s, is_anonymous=%s
            WHERE class_id=%s AND student_id=%s
            RETURNING *
            """,
            (
                (body.pseudonym or "").strip() or None,
                bool(body.is_anonymous and membership["allow_anonymous"]),
                class_id,
                str(current_user.id),
            ),
        )
        row = cur.fetchone()
        conn.commit()
    return dict(row)


@router.get("/student/classes", tags=["League"])
def list_student_classes(
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Acces interzis")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                c.id,
                c.name,
                c.class_code,
                c.allow_anonymous,
                c.created_at,
                u.full_name AS teacher_name,
                m.id AS membership_id,
                m.pseudonym,
                m.is_anonymous,
                m.joined_at
            FROM class_group_memberships m
            JOIN class_groups c ON c.id = m.class_id
            JOIN users u ON u.id = c.teacher_id
            WHERE m.student_id=%s AND m.is_active=TRUE
            ORDER BY m.joined_at DESC
            """,
            (str(current_user.id),),
        )
        return [dict(row) for row in cur.fetchall()]


@router.get("/league/classes/{class_id}/overview", tags=["League"])
def get_class_league_overview(
    class_id: str,
    week_start: Optional[str] = None,
    conn: Connection = Depends(get_db_conn),
    current_user: UserDB = Depends(get_current_user),
):
    if current_user.role not in (UserRole.STUDENT, UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Acces interzis")

    viewer_id = str(current_user.id)
    is_teacher_view = current_user.role in (UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT c.*, u.full_name AS teacher_name,
                   COUNT(m.id) FILTER (WHERE m.is_active=TRUE) AS member_count
            FROM class_groups c
            JOIN users u ON u.id = c.teacher_id
            LEFT JOIN class_group_memberships m ON m.class_id = c.id
            WHERE c.id=%s
            GROUP BY c.id, u.full_name
            """,
            (class_id,),
        )
        class_row = cur.fetchone()

    if not class_row:
        raise HTTPException(status_code=404, detail="Clasa nu există")

    if current_user.role in (UserRole.TEACHER, UserRole.SCHOOL_TEACHER) and str(class_row["teacher_id"]) != viewer_id:
        raise HTTPException(status_code=403, detail="Nu ai acces la această clasă")
    if current_user.role == UserRole.STUDENT:
        _ensure_student_membership(conn, class_id, viewer_id)

    start, end = _week_bounds(week_start)
    leaderboard = _build_leaderboard(conn, class_id, viewer_id, start, end, is_teacher_view)
    challenges = _build_challenges(conn, class_id, viewer_id, start, end, is_teacher_view)

    my_membership = None
    if current_user.role == UserRole.STUDENT:
        my_membership = _ensure_student_membership(conn, class_id, viewer_id)

    return {
        "class_info": {
            "id": str(class_row["id"]),
            "name": class_row["name"],
            "class_code": class_row["class_code"],
            "allow_anonymous": class_row["allow_anonymous"],
            "teacher_name": class_row["teacher_name"],
            "member_count": int(class_row["member_count"] or 0),
        },
        "week": {"start": str(start), "end": str(end)},
        "my_membership": my_membership,
        "leaderboard": leaderboard,
        "challenges": challenges,
    }
