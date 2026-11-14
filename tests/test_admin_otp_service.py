
import tempfile
import unittest
from pathlib import Path

from services.admin_otp_service import AdminOTPService


class TestAdminOTPService(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.mailbox = Path(
            self.directory.name
        ) / "admin_mailbox.txt"

        self.now = 100

        self.service = AdminOTPService(
            self.mailbox,
            ttl_seconds=120,
            clock=lambda: self.now
        )

    def get_code(self):
        content = self.mailbox.read_text(
            encoding="utf-8"
        )
        return content.split(": ")[1].strip()

    def test_request_and_verify(self):
        self.service.request_code()
        code = self.get_code()

        self.assertTrue(
            self.service.verify_code(code)
        )

    def test_otp_single_use(self):
        self.service.request_code()
        code = self.get_code()

        self.service.verify_code(code)

        with self.assertRaises(ValueError):
            self.service.verify_code(code)

    def test_otp_expiration(self):
        self.service.request_code()
        code = self.get_code()

        self.now += 121

        with self.assertRaises(ValueError):
            self.service.verify_code(code)

    def test_wrong_code(self):
        self.service.request_code()
        code = self.get_code()
        wrong = "000000" if code != "000000" else "999999"

        with self.assertRaises(ValueError):
            self.service.verify_code(wrong)

        self.assertTrue(
            self.service.verify_code(code)
        )


if __name__ == "__main__":
    unittest.main()
