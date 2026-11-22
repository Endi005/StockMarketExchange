
import tempfile
import unittest
from pathlib import Path

from services.admin_otp_service import AdminOTPService


class TestAdminOTPAttempts(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.mailbox = (
            Path(self.directory.name) / "admin_mailbox.txt"
        )

        self.now = 1000

        self.service = AdminOTPService(
            self.mailbox,
            ttl_seconds=120,
            clock=lambda: self.now
        )

    def request_valid_code(self):
        self.service.request_code()

        text = self.mailbox.read_text(
            encoding="utf-8"
        )

        return text.split(": ", 1)[1].strip()

    def incorrect_code(self, correct_code):
        if correct_code != "000000":
            return "000000"

        return "999999"

    def test_correct_code_succeeds(self):
        code = self.request_valid_code()

        self.assertTrue(
            self.service.verify_code(code)
        )

    def test_five_failures_still_allow_correct_code(self):
        code = self.request_valid_code()
        wrong = self.incorrect_code(code)

        for _ in range(5):
            with self.assertRaises(ValueError):
                self.service.verify_code(wrong)

        self.assertTrue(
            self.service.verify_code(code)
        )

    def test_six_failures_invalidate_code(self):
        code = self.request_valid_code()
        wrong = self.incorrect_code(code)

        for _ in range(6):
            with self.assertRaises(ValueError):
                self.service.verify_code(wrong)

        with self.assertRaisesRegex(ValueError, "No active OTP"):
            self.service.verify_code(code)

    def test_mailbox_deleted_after_six_failures(self):
        code = self.request_valid_code()
        wrong = self.incorrect_code(code)

        for _ in range(6):
            with self.assertRaises(ValueError):
                self.service.verify_code(wrong)

        self.assertFalse(self.mailbox.exists())

    def test_new_code_after_lockout(self):
        code = self.request_valid_code()
        wrong = self.incorrect_code(code)

        for _ in range(6):
            with self.assertRaises(ValueError):
                self.service.verify_code(wrong)

        new_code = self.request_valid_code()

        self.assertTrue(
            self.service.verify_code(new_code)
        )

    def test_successful_code_cannot_be_reused(self):
        code = self.request_valid_code()

        self.service.verify_code(code)

        with self.assertRaises(ValueError):
            self.service.verify_code(code)

    def test_expired_code_is_rejected(self):
        code = self.request_valid_code()

        self.now += 121

        with self.assertRaisesRegex(ValueError, "expired"):
            self.service.verify_code(code)

        self.assertFalse(self.mailbox.exists())

    def test_invalid_input_counts_as_failure(self):
        code = self.request_valid_code()

        for _ in range(6):
            with self.assertRaises(ValueError):
                self.service.verify_code(None)

        with self.assertRaisesRegex(ValueError, "No active OTP"):
            self.service.verify_code(code)


if __name__ == "__main__":
    unittest.main()
