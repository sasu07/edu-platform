import hashlib
import secrets
import uuid
from datetime import datetime as dt, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from psycopg import Connection
from psycopg.errors import UniqueViolation
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
from email_service import send_password_setup_email, send_welcome_email
from models import (
    AdminUserCreate,
    AdminUserRoleUpdate,
    PasswordResetComplete,
    SubscriptionDB,
    Token,
    UserDB,
    UserLogin,
    UserRegister,
    UserRole,
)

router = APIRouter()

_ADMIN_MANAGED_ROLES = (
    UserRole.STUDENT,
    UserRole.TEACHER,
    UserRole.SCHOOL_TEACHER,
    UserRole.PARENT,
)
_ADMIN_MANAGED_ROLE_VALUES = {role.value for role in _ADMIN_MANAGED_ROLES}
_INVITE_TTL = timedelta(hours=24)
_RESET_TTL = timedelta(minutes=30)


def _audit_auth(request: Request, action: str, **kw) -> None:
    write_audit(
        action,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        **kw,
    )


def _normalise_email(email: str) -> str:
    value = email.strip().lower()
    if value.count("@") != 1 or any(char.isspace() for char in value):
        raise HTTPException(status_code=422, detail="Adresa de email nu este validă")
    local, domain = value.split("@", 1)
    local_allowed = set("abcdefghijklmnopqrstuvwxyz0123456789.!#$%&'*+/=?^_`{|}~-")
    if (
        not local
        or len(local) > 64
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
        or any(char not in local_allowed for char in local)
    ):
        raise HTTPException(status_code=422, detail="Adresa de email nu este validă")
    domain_labels = domain.split(".")
    if len(domain) > 253 or len(domain_labels) < 2 or any(
        not label
        or len(label) > 63
        or label.startswith("-")
        or label.endswith("-")
        or any(not (char.isalnum() or char == "-") for char in label)
        for label in domain_labels
    ):
        raise HTTPException(status_code=422, detail="Adresa de email nu este validă")
    return value


def _reset_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_password_token(
    conn: Connection,
    *,
    user_id: str,
    purpose: str,
    created_by: Optional[str],
) -> str:
    """Creează un token one-time; în DB persistă exclusiv digestul SHA-256."""
    if purpose not in ("invite", "reset"):
        raise ValueError("Scop invalid pentru token")

    raw_token = secrets.token_urlsafe(32)
    expires_at = dt.now(timezone.utc) + (_INVITE_TTL if purpose == "invite" else _RESET_TTL)
    with conn.cursor() as cur:
        # Un singur link activ per utilizator. Folosirea unuia dintre linkuri
        # invalidează implicit toate cererile mai vechi.
        cur.execute(
            """
            UPDATE password_reset_tokens
            SET used_at = NOW()
            WHERE user_id = %s AND used_at IS NULL
            """,
            (user_id,),
        )
        cur.execute(
            """
            INSERT INTO password_reset_tokens
                (user_id, token_hash, purpose, expires_at, created_by)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, _reset_token_hash(raw_token), purpose, expires_at, created_by),
        )
    return raw_token


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
            """
            SELECT id, email, full_name, role, is_active, created_at,
                   password_hash, auth_version
            FROM users WHERE email = %s
            """,
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

    auth_version = row.pop("auth_version", 0)
    user = UserDB(**{k: v for k, v in row.items() if k != "password_hash"})
    token = create_access_token(str(user.id), user.role.value, auth_version)
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


@router.post(
    "/admin/users",
    response_model=UserDB,
    status_code=status.HTTP_201_CREATED,
    tags=["Admin"],
)
@limiter.limit("10/minute")
def create_admin_user(
    request: Request,
    body: AdminUserCreate,
    admin: UserDB = Depends(require_role(UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    """Creează un cont fără ca administratorul să cunoască parola."""
    if body.role not in _ADMIN_MANAGED_ROLES:
        raise HTTPException(status_code=400, detail="Rolul nu poate fi gestionat din panoul de administrare")

    email = _normalise_email(body.email)
    full_name = body.full_name.strip()
    if not full_name:
        raise HTTPException(status_code=422, detail="Numele complet este obligatoriu")

    # Hashul inițial corespunde unui secret aleator care nu este returnat și nu
    # este transmis nimănui. Contul rămâne inactiv până la folosirea invitației.
    unusable_password_hash = hash_password(secrets.token_urlsafe(48))

    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(%s)", (email,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Email deja înregistrat")

            cur.execute(
                """
                INSERT INTO users (email, password_hash, full_name, role, is_active, invite_pending)
                VALUES (%s, %s, %s, %s, FALSE, TRUE)
                RETURNING id, email, full_name, role, is_active, created_at
                """,
                (email, unusable_password_hash, full_name, body.role.value),
            )
            user_row = cur.fetchone()

            if body.role in (UserRole.STUDENT, UserRole.SCHOOL_TEACHER):
                cur.execute(
                    "INSERT INTO subscriptions (user_id, plan_type, status) VALUES (%s, 'free', 'active')",
                    (str(user_row["id"]),),
                )

        raw_token = _issue_password_token(
            conn,
            user_id=str(user_row["id"]),
            purpose="invite",
            created_by=str(admin.id),
        )
        conn.commit()
    except UniqueViolation as exc:
        conn.rollback()
        raise HTTPException(status_code=409, detail="Email deja înregistrat") from exc

    email_sent = send_password_setup_email(email, full_name, raw_token, "invite")
    if not email_sent:
        _audit_auth(
            request,
            "admin.user.create_email_failed",
            actor_user_id=str(admin.id),
            actor_role=admin.role.value,
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"target_user_id": str(user_row["id"]), "target_email": email},
        )
        raise HTTPException(
            status_code=503,
            detail="Contul a fost creat, dar invitația nu a putut fi trimisă. Retrimite invitația din lista de utilizatori.",
        )

    _audit_auth(
        request,
        "admin.user.create",
        actor_user_id=str(admin.id),
        actor_role=admin.role.value,
        status=status.HTTP_201_CREATED,
        details={
            "target_user_id": str(user_row["id"]),
            "target_email": email,
            "role": body.role.value,
        },
    )
    return UserDB(**user_row)


@router.patch("/admin/users/{user_id}/role", response_model=UserDB, tags=["Admin"])
def update_admin_user_role(
    request: Request,
    user_id: uuid.UUID,
    body: AdminUserRoleUpdate,
    admin: UserDB = Depends(require_role(UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    """Schimbă numai roluri neprivilegiate și invalidează sesiunile țintei."""
    if str(user_id) == str(admin.id):
        raise HTTPException(status_code=400, detail="Nu îți poți schimba propriul rol")
    if body.role not in _ADMIN_MANAGED_ROLES:
        raise HTTPException(status_code=400, detail="Rolul nu poate fi gestionat din panoul de administrare")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, email, full_name, role, is_active, created_at
            FROM users WHERE id = %s
            FOR UPDATE
            """,
            (str(user_id),),
        )
        target = cur.fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Utilizator inexistent")
        if target["role"] not in _ADMIN_MANAGED_ROLE_VALUES:
            raise HTTPException(status_code=403, detail="Rolurile privilegiate nu pot fi modificate aici")

        old_role = target["role"]
        if old_role == body.role.value:
            conn.commit()
            return UserDB(**target)

        # Relațiile părinte–elev sunt valide numai cât timp capetele lor au
        # rolurile aferente. Eliminarea lor previne accesul rezidual la date.
        if old_role == UserRole.PARENT.value and body.role != UserRole.PARENT:
            cur.execute("DELETE FROM parent_student WHERE parent_id = %s", (str(user_id),))
        if old_role == UserRole.STUDENT.value and body.role != UserRole.STUDENT:
            cur.execute("DELETE FROM parent_student WHERE student_id = %s", (str(user_id),))

        cur.execute(
            """
            UPDATE users
            SET role = %s, auth_version = auth_version + 1, updated_at = NOW()
            WHERE id = %s
            RETURNING id, email, full_name, role, is_active, created_at
            """,
            (body.role.value, str(user_id)),
        )
        updated = cur.fetchone()

        if body.role in (UserRole.STUDENT, UserRole.SCHOOL_TEACHER):
            cur.execute(
                """
                INSERT INTO subscriptions (user_id, plan_type, status)
                SELECT %s, 'free', 'active'
                WHERE NOT EXISTS (
                    SELECT 1 FROM subscriptions
                    WHERE user_id = %s AND status = 'active'
                )
                """,
                (str(user_id), str(user_id)),
            )
        else:
            cur.execute(
                "SELECT plan_type FROM subscriptions WHERE user_id = %s AND status = 'active'",
                (str(user_id),),
            )
            active_plans = [row["plan_type"] for row in cur.fetchall()]
            cur.execute(
                """
                UPDATE subscriptions
                SET status = 'cancelled', updated_at = NOW()
                WHERE user_id = %s AND status = 'active'
                """,
                (str(user_id),),
            )
            if active_plans:
                cur.execute(
                    "DELETE FROM user_exercise_sets WHERE user_id = %s AND linked_plan = ANY(%s)",
                    (str(user_id), active_plans),
                )
        conn.commit()

    _audit_auth(
        request,
        "admin.user.role_change",
        actor_user_id=str(admin.id),
        actor_role=admin.role.value,
        status=200,
        details={
            "target_user_id": str(user_id),
            "old_role": old_role,
            "new_role": body.role.value,
        },
    )
    return UserDB(**updated)


@router.post(
    "/admin/users/{user_id}/password-reset",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Admin"],
)
@limiter.limit("10/minute")
def request_admin_password_reset(
    request: Request,
    user_id: uuid.UUID,
    admin: UserDB = Depends(require_role(UserRole.ADMIN)),
    conn: Connection = Depends(get_db_conn),
):
    """Trimite linkul fără a expune tokenul sau o parolă administratorului."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT u.id, u.email, u.full_name, u.role, u.is_active, u.invite_pending
            FROM users u
            WHERE u.id = %s
            FOR UPDATE
            """,
            (str(user_id),),
        )
        target = cur.fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Utilizator inexistent")
        if target["role"] not in _ADMIN_MANAGED_ROLE_VALUES:
            raise HTTPException(status_code=403, detail="Parola unui cont privilegiat nu poate fi resetată aici")

    if not target["is_active"] and not target["invite_pending"]:
        raise HTTPException(
            status_code=409,
            detail="Contul este dezactivat și nu poate fi reactivat prin resetarea parolei.",
        )

    purpose = "invite" if target["invite_pending"] else "reset"
    raw_token = _issue_password_token(
        conn,
        user_id=str(user_id),
        purpose=purpose,
        created_by=str(admin.id),
    )
    conn.commit()
    email_sent = send_password_setup_email(
        target["email"], target["full_name"], raw_token, purpose
    )
    if not email_sent:
        _audit_auth(
            request,
            "admin.user.password_reset_email_failed",
            actor_user_id=str(admin.id),
            actor_role=admin.role.value,
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"target_user_id": str(user_id), "purpose": purpose},
        )
        raise HTTPException(
            status_code=503,
            detail="Linkul a fost creat, dar emailul nu a putut fi trimis. Încearcă din nou.",
        )
    _audit_auth(
        request,
        "admin.user.password_reset_requested",
        actor_user_id=str(admin.id),
        actor_role=admin.role.value,
        status=status.HTTP_202_ACCEPTED,
        details={"target_user_id": str(user_id), "purpose": purpose},
    )
    return {"message": "Linkul pentru alegerea parolei a fost trimis pe email."}


@router.post(
    "/auth/password-reset/complete",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    tags=["Auth"],
)
@limiter.limit("10/minute")
def complete_password_reset(
    request: Request,
    body: PasswordResetComplete,
    conn: Connection = Depends(get_db_conn),
):
    # bcrypt acceptă maximum 72 de octeți, nu 72 de caractere Unicode.
    if len(body.new_password.encode("utf-8")) > 72:
        raise HTTPException(status_code=422, detail="Parola este prea lungă")

    new_password_hash = hash_password(body.new_password)
    token_hash = _reset_token_hash(body.token.strip())

    with conn.cursor(row_factory=dict_row) as cur:
        # FOR UPDATE + condițiile de valabilitate fac operația one-time inclusiv
        # când două requesturi încearcă simultan același token.
        cur.execute(
            """
            SELECT prt.user_id, prt.purpose, u.email, u.full_name, u.role,
                   u.is_active, u.invite_pending
            FROM password_reset_tokens prt
            JOIN users u ON u.id = prt.user_id
            WHERE prt.token_hash = %s
              AND prt.used_at IS NULL
              AND prt.expires_at > NOW()
            FOR UPDATE OF prt
            """,
            (token_hash,),
        )
        token_row = cur.fetchone()
        if not token_row:
            raise HTTPException(status_code=400, detail="Link invalid, expirat sau deja folosit")
        if token_row["purpose"] == "invite" and not token_row["invite_pending"]:
            raise HTTPException(status_code=400, detail="Link invalid, expirat sau deja folosit")

        cur.execute(
            """
            UPDATE users
            SET password_hash = %s,
                is_active = CASE WHEN %s = 'invite' THEN TRUE ELSE is_active END,
                invite_pending = CASE WHEN %s = 'invite' THEN FALSE ELSE invite_pending END,
                auth_version = auth_version + 1,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                new_password_hash,
                token_row["purpose"],
                token_row["purpose"],
                str(token_row["user_id"]),
            ),
        )
        cur.execute(
            """
            UPDATE password_reset_tokens
            SET used_at = NOW()
            WHERE user_id = %s AND used_at IS NULL
            """,
            (str(token_row["user_id"]),),
        )
        conn.commit()

    _audit_auth(
        request,
        "auth.password_reset_completed",
        actor_user_id=str(token_row["user_id"]),
        actor_role=token_row["role"],
        status=status.HTTP_204_NO_CONTENT,
        details={"purpose": token_row["purpose"]},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
            SELECT u.id, u.email, u.full_name, u.role, u.is_active, u.invite_pending, u.created_at,
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
