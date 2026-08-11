"""Smoke test end-to-end pentru administrarea utilizatorilor în mediul local.

Rulează numai împotriva localhost și verifică API-ul, Mailpit, invitația,
schimbarea rolului, resetarea parolei și invalidarea JWT-urilor vechi.
Nu este inclus în testele unitare automate deoarece necesită stack-ul Docker.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


def _json_request(
    base_url: str,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    expected: tuple[int, ...] = (200,),
) -> tuple[int, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            status = response.status
            raw = response.read()
    except HTTPError as error:
        status = error.code
        raw = error.read()

    parsed: Any = None
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw.decode("utf-8", errors="replace")
    if status not in expected:
        raise AssertionError(f"{method} {path}: așteptat {expected}, primit {status}: {parsed}")
    return status, parsed


def _mailpit_json(mailpit_url: str, path: str) -> Any:
    with urlopen(f"{mailpit_url}{path}", timeout=10) as response:
        return json.loads(response.read())


def _wait_for_reset_token(
    mailpit_url: str,
    recipient: str,
    *,
    excluded_ids: set[str] | None = None,
) -> tuple[str, str]:
    excluded_ids = excluded_ids or set()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        listing = _mailpit_json(mailpit_url, "/api/v1/messages")
        for message in listing.get("messages", []):
            message_id = str(message.get("ID") or message.get("id") or "")
            if not message_id or message_id in excluded_ids:
                continue
            recipients = json.dumps(message.get("To") or message.get("to") or "")
            if recipient.lower() not in recipients.lower():
                continue
            detail = _mailpit_json(mailpit_url, f"/api/v1/message/{message_id}")
            content = html.unescape(str(detail.get("HTML") or detail.get("Text") or detail))
            match = re.search(r"/reset-password#token=([^\"'<>\s]+)", content)
            if match:
                return unquote(match.group(1)), message_id
        time.sleep(0.4)
    raise AssertionError(f"Mailpit nu a primit linkul pentru {recipient}")


def run(api_url: str, mailpit_url: str, admin_password: str) -> dict[str, Any]:
    admin_login = _json_request(
        api_url,
        "POST",
        "/auth/login",
        payload={"email": "admin@test.local", "password": admin_password},
    )[1]
    admin_token = admin_login["access_token"]
    admin_id = admin_login["user"]["id"]

    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    email = f"mobil.admin.flow.{suffix}@example.test"
    first_password = "MobilUser!2026"
    second_password = "MobilUser!2027"

    created = _json_request(
        api_url,
        "POST",
        "/admin/users",
        payload={"full_name": "Utilizator Mobil Test", "email": email, "role": "student"},
        token=admin_token,
        expected=(201,),
    )[1]
    assert created["is_active"] is False
    assert "password" not in created and "token" not in created
    user_id = created["id"]

    invite_token, invite_message_id = _wait_for_reset_token(mailpit_url, email)
    _json_request(
        api_url,
        "POST",
        "/auth/password-reset/complete",
        payload={"token": invite_token, "new_password": first_password},
        expected=(204,),
    )

    user_login = _json_request(
        api_url,
        "POST",
        "/auth/login",
        payload={"email": email, "password": first_password},
    )[1]
    first_user_token = user_login["access_token"]
    assert user_login["user"]["role"] == "student"

    _json_request(
        api_url,
        "POST",
        f"/admin/subscriptions/{user_id}/upgrade?plan_type=premium_help",
        token=admin_token,
        expected=(200,),
    )

    changed = _json_request(
        api_url,
        "PATCH",
        f"/admin/users/{user_id}/role",
        payload={"role": "parent"},
        token=admin_token,
    )[1]
    assert changed["role"] == "parent"
    _json_request(api_url, "GET", "/auth/me", token=first_user_token, expected=(401,))

    parent_login = _json_request(
        api_url,
        "POST",
        "/auth/login",
        payload={"email": email, "password": first_password},
    )[1]
    assert parent_login["user"]["role"] == "parent"
    parent_token = parent_login["access_token"]

    _json_request(
        api_url,
        "POST",
        f"/admin/users/{user_id}/password-reset",
        token=admin_token,
        expected=(202,),
    )
    reset_token, _ = _wait_for_reset_token(
        mailpit_url,
        email,
        excluded_ids={invite_message_id},
    )
    _json_request(
        api_url,
        "POST",
        "/auth/password-reset/complete",
        payload={"token": reset_token, "new_password": second_password},
        expected=(204,),
    )

    _json_request(api_url, "GET", "/auth/me", token=parent_token, expected=(401,))
    _json_request(
        api_url,
        "POST",
        "/auth/login",
        payload={"email": email, "password": first_password},
        expected=(401,),
    )
    final_login = _json_request(
        api_url,
        "POST",
        "/auth/login",
        payload={"email": email, "password": second_password},
    )[1]
    assert final_login["user"]["role"] == "parent"
    access_after_role_change = _json_request(
        api_url, "GET", "/auth/me/access", token=final_login["access_token"]
    )[1]
    assert access_after_role_change == {
        "can_help_requests": False,
        "can_download_pdf": False,
        "can_unlimited_gen": False,
    }
    _json_request(
        api_url,
        "POST",
        "/help-requests/",
        payload={
            "exercise_id": "00000000-0000-0000-0000-000000000000",
            "flag_type": "WRITTEN",
            "notes": "verificare rol",
        },
        token=final_login["access_token"],
        expected=(403,),
    )

    _json_request(
        api_url,
        "POST",
        "/auth/password-reset/complete",
        payload={"token": reset_token, "new_password": second_password},
        expected=(400,),
    )

    _json_request(
        api_url,
        "PATCH",
        f"/admin/users/{user_id}/role",
        payload={"role": "admin"},
        token=admin_token,
        expected=(400,),
    )
    _json_request(
        api_url,
        "PATCH",
        f"/admin/users/{admin_id}/role",
        payload={"role": "student"},
        token=admin_token,
        expected=(400,),
    )
    _json_request(
        api_url,
        "POST",
        f"/admin/users/{admin_id}/password-reset",
        token=admin_token,
        expected=(403,),
    )

    child_email = f"mobil.admin.child.{suffix}@example.test"
    child = _json_request(
        api_url,
        "POST",
        "/admin/users",
        payload={"full_name": "Elev Legătură Test", "email": child_email, "role": "student"},
        token=admin_token,
        expected=(201,),
    )[1]
    child_id = child["id"]
    _json_request(
        api_url,
        "POST",
        "/admin/parent-student",
        payload={"parent_id": user_id, "student_id": child_id},
        token=admin_token,
        expected=(200,),
    )
    links_before = _json_request(
        api_url, "GET", "/admin/parent-students", token=admin_token
    )[1]
    assert any(link["parent_id"] == user_id and link["student_id"] == child_id for link in links_before)

    _json_request(
        api_url,
        "PATCH",
        f"/admin/users/{child_id}/role",
        payload={"role": "teacher"},
        token=admin_token,
    )
    links_after = _json_request(
        api_url, "GET", "/admin/parent-students", token=admin_token
    )[1]
    assert not any(link["parent_id"] == user_id and link["student_id"] == child_id for link in links_after)
    _json_request(
        api_url,
        "GET",
        f"/parent/students/{child_id}/stats",
        token=final_login["access_token"],
        expected=(403,),
    )
    _json_request(
        api_url,
        "POST",
        "/admin/parent-student",
        payload={"parent_id": user_id, "student_id": child_id},
        token=admin_token,
        expected=(400,),
    )

    listed_users = _json_request(
        api_url, "GET", "/admin/users", token=admin_token
    )[1]
    parent_row = next(account for account in listed_users if account["id"] == user_id)
    child_row = next(account for account in listed_users if account["id"] == child_id)
    assert parent_row["active_plans"] == []
    assert parent_row["invite_pending"] is False
    assert child_row["invite_pending"] is True

    return {
        "email": email,
        "user_id": user_id,
        "final_role": final_login["user"]["role"],
        "checks": [
            "invite email",
            "password setup",
            "role change",
            "JWT invalidation after role",
            "password reset email",
            "JWT invalidation after password",
            "one-time token",
            "privileged role protections",
            "premium access removed after role change",
            "parent-student link cleanup after role change",
            "invite state returned by admin API",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8001")
    parser.add_argument("--mailpit", default="http://127.0.0.1:8025")
    parser.add_argument("--admin-password", required=True)
    args = parser.parse_args()

    for label, url, expected_port in (
        ("API", args.api, 8001),
        ("Mailpit", args.mailpit, 8025),
    ):
        parsed = urlparse(url)
        if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != expected_port:
            raise SystemExit(f"{label} trebuie să fie serviciul local de test de pe portul {expected_port}")

    print(json.dumps(run(args.api.rstrip("/"), args.mailpit.rstrip("/"), args.admin_password), indent=2))


if __name__ == "__main__":
    main()
