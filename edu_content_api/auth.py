import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt
from jose import JWTError, jwt
from psycopg import Connection
from psycopg.rows import dict_row

from database import get_db_conn
from models import UserDB, UserRole

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "changeme-in-production-use-long-random-string")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 zile

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid sau expirat",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    conn: Connection = Depends(get_db_conn),
) -> UserDB:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autentificare necesară",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, email, full_name, role, is_active, created_at FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()

    if not row or not row["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilizator inexistent sau inactiv")

    return UserDB(**row)


def require_role(*roles: UserRole):
    """Dependency factory — permite accesul doar rolurilor specificate."""
    def _check(current_user: UserDB = Depends(get_current_user)) -> UserDB:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acces interzis. Rol necesar: {[r.value for r in roles]}",
            )
        return current_user
    return _check


def _has_help_access(user_id: str, conn: Connection) -> bool:
    """Returnează True dacă userul poate trimite cereri de ajutor (premium_help sau premium)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id FROM subscriptions
            WHERE user_id = %s
              AND plan_type IN ('premium', 'premium_help')
              AND status = 'active'
              AND (expires_at IS NULL OR expires_at > NOW())
            LIMIT 1
            """,
            (user_id,),
        )
        return cur.fetchone() is not None


def _has_active_premium(user_id: str, conn: Connection) -> bool:
    """Returnează True dacă userul are orice plan premium activ (help, pdf sau full)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id FROM subscriptions
            WHERE user_id = %s
              AND plan_type IN ('premium', 'premium_help', 'premium_pdf')
              AND status = 'active'
              AND (expires_at IS NULL OR expires_at > NOW())
            LIMIT 1
            """,
            (user_id,),
        )
        return cur.fetchone() is not None


def _has_pdf_access(user_id: str, conn: Connection) -> bool:
    """Returnează True dacă userul are acces la descărcare PDF (premium_pdf sau premium)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id FROM subscriptions
            WHERE user_id = %s
              AND plan_type IN ('premium', 'premium_pdf')
              AND status = 'active'
              AND (expires_at IS NULL OR expires_at > NOW())
            LIMIT 1
            """,
            (user_id,),
        )
        return cur.fetchone() is not None


def require_premium(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
) -> UserDB:
    """Verifică că userul poate trimite cereri de ajutor (Premium Help sau Premium Full)."""
    if current_user.role in (UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN):
        return current_user
    if _has_help_access(str(current_user.id), conn):
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Această funcționalitate necesită abonament Premium Help sau Premium Full",
    )


def require_pdf_premium(
    current_user: UserDB = Depends(get_current_user),
    conn: Connection = Depends(get_db_conn),
) -> UserDB:
    """Verifică că userul are acces la descărcare PDF (premium_pdf sau premium)."""
    if current_user.role in (UserRole.TEACHER, UserRole.SCHOOL_TEACHER, UserRole.ADMIN):
        return current_user
    if _has_pdf_access(str(current_user.id), conn):
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Descărcarea PDF necesită abonamentul Premium PDF",
    )


def check_school_teacher_limit(user_id: str, conn: Connection) -> None:
    """
    Verifică limita lunară de variante pentru school_teacher free (max 5/lună).
    Ridică 403 dacă limita e depășită.
    """
    if _has_active_premium(user_id, conn):
        return  # premium — fără limită

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT COUNT(*) as cnt FROM variants
            WHERE created_by_user_id_fk = %s
              AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
            """,
            (user_id,),
        )
        row = cur.fetchone()

    if row and row["cnt"] >= 5:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Limita de 5 variante/lună (plan Free) a fost atinsă. Upgrade la Premium pentru variante nelimitate.",
        )
