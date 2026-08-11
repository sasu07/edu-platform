import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pydantic import ValidationError


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import email_service  # noqa: E402
from models import PasswordResetComplete  # noqa: E402


AUTH_PATH = BACKEND_DIR / "auth.py"
ROUTER_PATH = BACKEND_DIR / "routers" / "auth_router.py"
MIGRATION_PATH = BACKEND_DIR / "migrations" / "019_admin_user_management.sql"
INVITE_STATE_MIGRATION_PATH = BACKEND_DIR / "migrations" / "020_admin_invite_state.sql"
INVITE_BACKFILL_MIGRATION_PATH = BACKEND_DIR / "migrations" / "021_backfill_expired_admin_invites.sql"


class PasswordResetModelTests(unittest.TestCase):
    def test_password_requires_at_least_twelve_characters(self):
        with self.assertRaises(ValidationError):
            PasswordResetComplete(token="t" * 43, new_password="prea-scurta")

        model = PasswordResetComplete(token="t" * 43, new_password="o-parola-lunga-2026")
        self.assertEqual(model.new_password, "o-parola-lunga-2026")

    def test_password_requires_a_letter_and_a_digit(self):
        with self.assertRaises(ValidationError):
            PasswordResetComplete(token="t" * 43, new_password="doarlitereparola")
        with self.assertRaises(ValidationError):
            PasswordResetComplete(token="t" * 43, new_password="123456789012")


class PasswordEmailTests(unittest.TestCase):
    def test_reset_link_uses_fragment_instead_of_query_string(self):
        token = "secret-token_-1234567890"
        with patch.object(email_service, "_send") as send:
            email_service.send_password_setup_email(
                "elev@example.test",
                "Elev Test",
                token,
                "reset",
            )

        html = send.call_args.args[2]
        self.assertIn("/reset-password#token=secret-token_-1234567890", html)
        self.assertNotIn("/reset-password?token=", html)

    def test_smtp_can_run_without_starttls_or_login_for_mailpit(self):
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        smtp.__exit__.return_value = False

        with (
            patch.object(email_service, "SMTP_HOST", "mailpit"),
            patch.object(email_service, "SMTP_PORT", 1025),
            patch.object(email_service, "SMTP_FROM", "no-reply@example.test"),
            patch.object(email_service, "SMTP_STARTTLS", False),
            patch.object(email_service, "SMTP_USER", ""),
            patch.object(email_service, "SMTP_PASS", ""),
            patch.object(email_service.smtplib, "SMTP", return_value=smtp),
        ):
            sent = email_service._send("elev@example.test", "Subiect", "<p>Mesaj</p>")

        smtp.starttls.assert_not_called()
        smtp.login.assert_not_called()
        smtp.sendmail.assert_called_once()
        self.assertTrue(sent)

    def test_missing_smtp_reports_delivery_failure(self):
        with patch.object(email_service, "SMTP_HOST", ""):
            self.assertFalse(email_service._send("elev@example.test", "Subiect", "<p>Mesaj</p>"))


class AdminUserSecurityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.auth_source = AUTH_PATH.read_text(encoding="utf-8")
        cls.router_source = ROUTER_PATH.read_text(encoding="utf-8")
        cls.migration_source = MIGRATION_PATH.read_text(encoding="utf-8")
        cls.invite_state_migration_source = INVITE_STATE_MIGRATION_PATH.read_text(encoding="utf-8")
        cls.invite_backfill_migration_source = INVITE_BACKFILL_MIGRATION_PATH.read_text(encoding="utf-8")

    def test_jwt_version_is_backward_compatible(self):
        self.assertIn('"ver": auth_version', self.auth_source)
        self.assertIn('payload.get("ver", 0)', self.auth_source)
        self.assertIn("auth_version FROM users", self.auth_source)

    def test_only_non_privileged_roles_are_managed(self):
        managed_block = self.router_source.split("_ADMIN_MANAGED_ROLES = (", 1)[1].split(")", 1)[0]
        self.assertIn("UserRole.STUDENT", managed_block)
        self.assertIn("UserRole.TEACHER", managed_block)
        self.assertIn("UserRole.SCHOOL_TEACHER", managed_block)
        self.assertIn("UserRole.PARENT", managed_block)
        self.assertNotIn("UserRole.ADMIN", managed_block)

    def test_secure_admin_and_reset_routes_exist(self):
        self.assertIn('@router.post(\n    "/admin/users"', self.router_source)
        self.assertIn('@router.patch("/admin/users/{user_id}/role"', self.router_source)
        self.assertIn('"/admin/users/{user_id}/password-reset"', self.router_source)
        self.assertIn('"/auth/password-reset/complete"', self.router_source)
        self.assertNotIn('@router.post("/admin/teachers"', self.router_source)

    def test_tokens_are_hashed_and_consumed_once(self):
        self.assertIn("hashlib.sha256", self.router_source)
        self.assertIn("FOR UPDATE OF prt", self.router_source)
        self.assertIn("prt.used_at IS NULL", self.router_source)
        self.assertIn("prt.expires_at > NOW()", self.router_source)
        self.assertIn("auth_version = auth_version + 1", self.router_source)

    def test_migration_has_session_version_and_hashed_token_table(self):
        self.assertIn("auth_version INTEGER NOT NULL DEFAULT 0", self.migration_source)
        self.assertIn("CREATE TABLE IF NOT EXISTS password_reset_tokens", self.migration_source)
        self.assertIn("token_hash CHAR(64) NOT NULL UNIQUE", self.migration_source)
        self.assertIn("purpose IN ('invite', 'reset')", self.migration_source)
        self.assertIn("used_at TIMESTAMPTZ", self.migration_source)

    def test_invites_are_distinct_from_disabled_accounts(self):
        self.assertIn("invite_pending BOOLEAN NOT NULL DEFAULT FALSE", self.invite_state_migration_source)
        self.assertIn("invite_pending", self.router_source)
        self.assertIn("Contul este dezactivat", self.router_source)
        self.assertIn("prt.used_at IS NULL", self.invite_backfill_migration_source)
        self.assertNotIn("prt.expires_at", self.invite_backfill_migration_source)

    def test_role_change_reconciles_parent_student_links(self):
        self.assertIn("DELETE FROM parent_student WHERE parent_id", self.router_source)
        self.assertIn("DELETE FROM parent_student WHERE student_id", self.router_source)
        self.assertIn("SET status = 'cancelled'", self.router_source)

    def test_premium_access_is_scoped_by_current_role(self):
        self.assertIn("AND u.role = 'student'", self.auth_source)
        self.assertIn("current_user.role != UserRole.STUDENT", self.auth_source)


if __name__ == "__main__":
    unittest.main()
