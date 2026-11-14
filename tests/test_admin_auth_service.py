
import tempfile
import unittest
from pathlib import Path

from services.admin_otp_service import AdminOTPService
from services.admin_auth_service import AdminAuthService


class TestAdminAuthService(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.mailbox = Path(
            self.directory.name
        ) / "admin_mailbox.txt"

        self.now = 100

        otp = AdminOTPService(
            self.mailbox,
            ttl_seconds=120,
            clock=lambda: self.now
        )

        self.auth = AdminAuthService(
            otp,
            "secureadmin123",
            session_ttl_seconds=900,
            clock=lambda: self.now
        )

    def get_code(self):
        content = self.mailbox.read_text(encoding="utf-8")
        return content.split(": ")[1].strip()

    def test_correct_admin_login(self):
        self.auth.request_otp("secureadmin123")
        result = self.auth.login(self.get_code())

        self.assertTrue(
            self.auth.require_admin(result["session_token"])
        )

    def test_wrong_admin_password(self):
        with self.assertRaises(ValueError):
            self.auth.request_otp("wrongpassword")

        self.assertFalse(self.mailbox.exists())

    def test_otp_cannot_be_reused(self):
        self.auth.request_otp("secureadmin123")
        code = self.get_code()

        self.auth.login(code)

        with self.assertRaises(ValueError):
            self.auth.login(code)

    def test_admin_session_expires(self):
        self.auth.request_otp("secureadmin123")
        token = self.auth.login(self.get_code())["session_token"]

        self.now += 901

        with self.assertRaises(ValueError):
            self.auth.require_admin(token)

    def test_logout(self):
        self.auth.request_otp("secureadmin123")
        token = self.auth.login(self.get_code())["session_token"]

        self.auth.logout(token)

        with self.assertRaises(ValueError):
            self.auth.require_admin(token)


if __name__ == "__main__":
    unittest.main()
