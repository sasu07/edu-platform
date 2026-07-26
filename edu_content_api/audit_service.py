"""Audit trail — jurnal de securitate/business în Postgres.

- write_audit(): scrie un eveniment (best-effort, nu ridică niciodată excepție).
- AuditMiddleware: middleware ASGI pur care auditează automat toate mutațiile
  (POST/PUT/DELETE/PATCH) + accesele refuzate (401/403). E ASGI pur (nu
  BaseHTTPMiddleware) ca să nu interfereze cu StreamingResponse / BackgroundTasks.
"""
import json
import re
from typing import Optional

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

from rate_limit import client_ip

_AUDIT_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
# Auditate explicit în cod (cu detalii mai bogate) → le sărim din middleware ca să nu dublăm
_SKIP_PATHS = {"/auth/login", "/auth/register"}
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def write_audit(
    action: str,
    *,
    actor_user_id: Optional[str] = None,
    actor_role: Optional[str] = None,
    method: Optional[str] = None,
    path: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: Optional[int] = None,
    details: Optional[dict] = None,
) -> None:
    """Scrie un eveniment de audit. Best-effort — o eroare de audit NU trebuie
    să strice cererea, deci înghițim orice excepție."""
    from database import conn_pool
    if conn_pool is None:
        return
    try:
        with conn_pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_log
                    (actor_user_id, actor_role, action, method, path,
                     resource_type, resource_id, ip, user_agent, status, details)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    actor_user_id, actor_role, action[:80], method, path,
                    resource_type, resource_id, ip,
                    (user_agent or "")[:500] or None,
                    status,
                    json.dumps(details) if details else None,
                ),
            )
            conn.commit()
    except Exception:
        pass


def actor_from_request(request: Request):
    """(user_id, role) din JWT-ul din header, best-effort. (None, None) dacă lipsește/invalid."""
    auth = request.headers.get("authorization", "")
    if auth[:7].lower() == "bearer ":
        try:
            from auth import decode_token
            payload = decode_token(auth[7:])
            return payload.get("sub"), payload.get("role")
        except Exception:
            return None, None
    return None, None


def _parse_path(path: str):
    """resource_type (primul segment) + resource_id (UUID găsit) + action normalizat
    (UUID-uri → :id, pentru grupare)."""
    segments = [s for s in path.split("/") if s]
    resource_type = segments[0] if segments else None
    resource_id = None
    tmpl = []
    for s in segments:
        if _UUID_RE.fullmatch(s):
            resource_id = s
            tmpl.append(":id")
        else:
            tmpl.append(s)
    return resource_type, resource_id, "/" + "/".join(tmpl)


class AuditMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        status_code = {"v": None}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code["v"] = message.get("status")
            await send(message)

        await self.app(scope, receive, send_wrapper)

        try:
            method = scope.get("method", "")
            path = scope.get("path", "")
            code = status_code["v"]
            if (method in _AUDIT_METHODS or code in (401, 403)) and path not in _SKIP_PATHS:
                request = Request(scope)
                actor_id, role = actor_from_request(request)
                rtype, rid, tmpl = _parse_path(path)
                await run_in_threadpool(
                    write_audit,
                    f"{method} {tmpl}",
                    actor_user_id=actor_id,
                    actor_role=role,
                    method=method,
                    path=path,
                    resource_type=rtype,
                    resource_id=rid,
                    ip=client_ip(request),
                    user_agent=request.headers.get("user-agent"),
                    status=code,
                )
        except Exception:
            pass
