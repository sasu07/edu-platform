import uuid
from datetime import datetime as dt
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from psycopg import Connection
from psycopg.rows import dict_row

from audit_service import write_audit
from rate_limit import client_ip, limiter

from auth import (
    _has_gen_access,
    _has_help_access,
    _has_pdf_access,
    create_access_token,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from database import get_db_conn
from email_service import send_welcome_email
from models import SubscriptionDB, Token, UserDB, UserLogin, UserRegister, UserRole

router = APIRouter()


def _audit_auth(request: Request, action: str, **kw) -> None:
    write_audit(
        action,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        **kw,
    )


@router.post("/auth/register", response_model=Token, tags=["Auth"])
@limiter.limit("10/minute")
def register(request: Request, body: UserRegister, background_tasks: BackgroundTasks, conn: Connection = Depends(get_db_conn)):
    allowed_roles = (UserRole.STUDENT, UserRole.SCHOOL_TEACHER)
    if body.role not in allowed_roles:
        raise HTTPException(status_code=400, detail="Conturile de profesor platformă se creează doar de administrator")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (body.email,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Email deja înregistrat")

        cur.execute(
            """
            INSERT INTO users (email, password_hash, full_name, role)
            VALUES (%s, %s, %s, %s)
            RETURNING id, email, full_name, role, is_active, created_at
            """,
            (body.email, hash_password(body.password), body.full_name, body.role.value),
        )
        user_row = cur.fetchone()
        cur.execute(
            "INSERT INTO subscriptions (user_id, plan_type, status) VALUES (%s, 'free', 'active')",
            (str(user_row["id"]),),
        )
        conn.commit()

    user = UserDB(**user_row)
    token = create_access_token(str(user.id), user.role.value)

    # Email de bun venit — în fundal, ca să nu blocheze/eșueze înregistrarea dacă SMTP-ul pică
    background_tasks.add_task(send_welcome_email, body.email, body.full_name)

    _audit_auth(request, "register", actor_user_id=str(user.id), actor_role=user.role.value,
                status=201, details={"email": user.email, "role": user.role.value})

    return Token(access_token=token, user=user)


@router.post("/auth/login", response_model=Token, tags=["Auth"])
@limiter.limit("20/minute")
def login(request: Request, body: UserLogin, conn: Connection = Depends(get_db_conn)):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, email, full_name, role, is_active, created_at, password_hash FROM users WHERE email = %s",
            (body.email,),
        )
        row = cur.fetchone()

    if not row or not verify_password(body.password, row["password_hash"]):
        _audit_auth(request, "login.fail", status=401, details={"email": body.email})
        raise HTTPException(status_code=401, detail="Email sau parolă incorectă")
    if not row["is_active"]:
        _audit_auth(request, "login.fail", actor_user_id=str(row["id"]), status=403,
                    details={"email": body.email, "reason": "cont dezactivat"})
        raise HTTPException(status_code=403, detail="Cont dezactivat")

    user = UserDB(**{k: v for k, v in row.items() if k != "password_hash"})
    token = create_access_token(str(user.id), user.role.value)
    _audit_auth(request, "login.success", actor_user_id=str(user.id), actor_role=user.role.value,
                status=200, details={"email": user.email})
    return Token(access_token=token, user=user)


@router.get("/auth/me", response_model=UserDB, tags=["Auth"])
def me(current_user: UserDB = Depends(get_current_user)):
    return current_user


@router.get("/auth/me/access", tags=["Auth"])
def my_access(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    is_staff = current_user.role in ("teacher", "school_teacher", "admin")
    return {
        "can_help_requests": is_staff or _has_help_access(str(current_user.id), conn),
        "can_download_pdf": is_staff or _has_pdf_access(str(current_user.id), conn),
        "can_unlimited_gen": is_staff or _has_gen_access(str(current_user.id), conn),
    }


@router.get("/auth/me/limits", tags=["Auth"])
def my_limits(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    is_staff = current_user.role in ("teacher", "school_teacher", "admin")
    has_gen = is_staff or _has_gen_access(str(current_user.id), conn)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT COUNT(*) as cnt FROM exercise_generation_logs
            WHERE user_id = %s
              AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
            """,
            (str(current_user.id),),
        )
        ex_row = cur.fetchone()

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT COUNT(*) as cnt FROM variants
            WHERE created_by_user_id_fk = %s
              AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
            """,
            (str(current_user.id),),
        )
        var_row = cur.fetchone()

    ex_used = ex_row["cnt"] if ex_row else 0
    var_used = var_row["cnt"] if var_row else 0

    return {
        "exercise_gen_used": ex_used,
        "exercise_gen_limit": None if has_gen else 3,
        "variant_gen_used": var_used,
        "variant_gen_limit": None if has_gen else 1,
        "has_unlimited_gen": has_gen,
    }


@router.get("/auth/me/subscription", response_model=SubscriptionDB, tags=["Auth"])
def my_subscription(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, user_id, plan_type, status, expires_at, created_at
            FROM subscriptions
            WHERE user_id = %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (str(current_user.id),),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Niciun abonament găsit")
    return SubscriptionDB(**row)


@router.post("/admin/teachers", response_model=UserDB, tags=["Admin"])
def create_teacher(
    body: UserRegister,
    _admin: UserDB = Depends(require_role(UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (body.email,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Email deja înregistrat")

        cur.execute(
            """
            INSERT INTO users (email, password_hash, full_name, role)
            VALUES (%s, %s, %s, 'teacher')
            RETURNING id, email, full_name, role, is_active, created_at
            """,
            (body.email, hash_password(body.password), body.full_name),
        )
        user_row = cur.fetchone()
        conn.commit()

    return UserDB(**user_row)


@router.get("/admin/teachers", tags=["Admin"])
def list_teachers(
    _admin: UserDB = Depends(require_role(UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, full_name, email FROM users WHERE role = 'teacher' ORDER BY full_name"
        )
        return cur.fetchall()


@router.post("/admin/subscriptions/{user_id}/upgrade", response_model=SubscriptionDB, tags=["Admin"])
def upgrade_subscription(
    user_id: uuid.UUID,
    plan_type: str = "premium",
    expires_at: Optional[str] = None,
    _admin: UserDB = Depends(require_role(UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    valid_plans = ("premium", "premium_help", "premium_pdf", "premium_gen", "free")
    if plan_type not in valid_plans:
        raise HTTPException(status_code=400, detail=f"Plan invalid. Valori acceptate: {valid_plans}")
    exp = dt.fromisoformat(expires_at) if expires_at else None

    with conn.cursor(row_factory=dict_row) as cur:
        if plan_type == "premium":
            cur.execute(
                "UPDATE subscriptions SET status = 'cancelled', updated_at = NOW() WHERE user_id = %s AND status = 'active'",
                (str(user_id),),
            )
        else:
            cur.execute(
                "UPDATE subscriptions SET status = 'cancelled', updated_at = NOW() WHERE user_id = %s AND plan_type = %s AND status = 'active'",
                (str(user_id), plan_type),
            )
        cur.execute(
            """
            INSERT INTO subscriptions (user_id, plan_type, status, expires_at)
            VALUES (%s, %s, 'active', %s)
            RETURNING id, user_id, plan_type, status, expires_at, created_at
            """,
            (str(user_id), plan_type, exp),
        )
        row = cur.fetchone()
        conn.commit()
    return SubscriptionDB(**row)


@router.delete("/admin/subscriptions/{user_id}", tags=["Admin"])
def cancel_subscription(
    user_id: uuid.UUID,
    _admin: UserDB = Depends(require_role(UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT plan_type FROM subscriptions WHERE user_id = %s AND status = 'active'",
            (str(user_id),),
        )
        active_plans = [r["plan_type"] for r in cur.fetchall()]

        cur.execute(
            """
            UPDATE subscriptions
            SET status = 'cancelled', updated_at = NOW()
            WHERE user_id = %s AND status = 'active'
            RETURNING id
            """,
            (str(user_id),),
        )
        cancelled = cur.fetchall()

        if active_plans:
            cur.execute(
                "DELETE FROM user_exercise_sets WHERE user_id = %s AND linked_plan = ANY(%s)",
                (str(user_id), active_plans),
            )

        conn.commit()
    return {"cancelled": len(cancelled)}


@router.get("/admin/users", tags=["Admin"])
def list_users(
    _admin: UserDB = Depends(require_role(UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT u.id, u.email, u.full_name, u.role, u.is_active, u.created_at,
                   COALESCE(
                       (SELECT json_agg(plan_type ORDER BY created_at DESC)
                        FROM subscriptions
                        WHERE user_id = u.id
                          AND status = 'active'
                          AND (expires_at IS NULL OR expires_at > NOW())
                          AND plan_type != 'free'),
                       '[]'::json
                   ) AS active_plans
            FROM users u
            ORDER BY u.created_at DESC
            """
        )
        return cur.fetchall()


@router.post("/exercise-generations/log", tags=["Exercises"])
def log_exercise_generation(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
):
    is_staff = current_user.role in ("teacher", "school_teacher", "admin")

    if not is_staff and not _has_gen_access(str(current_user.id), conn):
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT COUNT(*) as cnt FROM exercise_generation_logs
                WHERE user_id = %s
                  AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
                """,
                (str(current_user.id),),
            )
            row = cur.fetchone()

        if row and row["cnt"] >= 3:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Limita de 3 generări de exerciții/lună (plan Free) a fost atinsă. Upgrade la Premium Gen pentru generare nelimitată.",
            )

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO exercise_generation_logs (user_id) VALUES (%s)",
            (str(current_user.id),),
        )
    conn.commit()
    return {"ok": True}


@router.get("/admin/audit", tags=["Admin"])
def list_audit(
    action: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    method: Optional[str] = None,
    status_code: Optional[int] = None,
    resource_type: Optional[str] = None,
    q: Optional[str] = None,          # căutare în path
    since_hours: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    _admin: UserDB = Depends(require_role(UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    """Jurnalul de audit — doar admin. Filtre opționale + paginare."""
    conditions: list = []
    params: list = []
    if action:
        conditions.append("al.action = %s"); params.append(action)
    if actor_user_id:
        conditions.append("al.actor_user_id = %s"); params.append(actor_user_id)
    if method:
        conditions.append("al.method = %s"); params.append(method.upper())
    if status_code is not None:
        conditions.append("al.status = %s"); params.append(status_code)
    if resource_type:
        conditions.append("al.resource_type = %s"); params.append(resource_type)
    if q:
        conditions.append("al.path ILIKE %s"); params.append(f"%{q}%")
    if since_hours:
        conditions.append("al.created_at >= NOW() - (%s || ' hours')::interval"); params.append(str(since_hours))

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM audit_log al{where}", tuple(params))
        total = cur.fetchone()["total"]
        cur.execute(
            f"""
            SELECT al.id, al.created_at, al.actor_user_id, al.actor_role, al.action,
                   al.method, al.path, al.resource_type, al.resource_id, al.ip,
                   al.status, al.details,
                   u.email AS actor_email, u.full_name AS actor_name
            FROM audit_log al
            LEFT JOIN users u ON u.id = al.actor_user_id
            {where}
            ORDER BY al.created_at DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params) + (limit, offset),
        )
        items = cur.fetchall()

    return {"total": total, "limit": limit, "offset": offset, "items": items}

