import tempfile
import threading
import unittest

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from services.admin_auth_service import AdminAuthService
from services.admin_otp_service import AdminOTPService


class TestAdminConcurrency(unittest.TestCase):

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)

        self.mailbox = (
            Path(self.temp_directory.name)
            / "admin_mailbox.txt"
        )

        self.password = "SecureAdmin123!"

        self.otp_service = AdminOTPService(
            self.mailbox
        )

        self.auth = AdminAuthService(
            self.otp_service,
            self.password
        )

    def read_otp(self):
        return (
            self.mailbox.read_text(encoding="utf-8")
            .strip()
            .rsplit(" ", 1)[-1]
        )

    def create_admin_session(self):
        self.auth.request_otp(self.password)

        result = self.auth.login(
            self.read_otp()
        )

        return result["session_token"]

    def test_slow_otp_generation_does_not_block_session(self):
        token = self.create_admin_session()

        started = threading.Event()
        release = threading.Event()

        original_request = self.otp_service.request_code

        def slow_request():
            started.set()

            if not release.wait(timeout=5):
                raise TimeoutError("Test release timed out.")

            return original_request()

        with patch.object(
            self.otp_service,
            "request_code",
            side_effect=slow_request
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:

                otp_future = pool.submit(
                    self.auth.request_otp,
                    self.password
                )

                try:
                    self.assertTrue(
                        started.wait(timeout=3)
                    )

                    session_future = pool.submit(
                        self.auth.require_admin,
                        token
                    )

                    self.assertTrue(
                        session_future.result(timeout=2)
                    )

                finally:
                    release.set()

                otp_future.result(timeout=5)

    def test_slow_otp_verification_does_not_block_session(self):
        token = self.create_admin_session()

        self.auth.request_otp(self.password)
        code = self.read_otp()

        started = threading.Event()
        release = threading.Event()

        original_verify = self.otp_service.verify_code

        def slow_verify(received_code):
            started.set()

            if not release.wait(timeout=5):
                raise TimeoutError("Test release timed out.")

            return original_verify(received_code)

        with patch.object(
            self.otp_service,
            "verify_code",
            side_effect=slow_verify
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:

                login_future = pool.submit(
                    self.auth.login,
                    code
                )

                try:
                    self.assertTrue(
                        started.wait(timeout=3)
                    )

                    session_future = pool.submit(
                        self.auth.require_admin,
                        token
                    )

                    self.assertTrue(
                        session_future.result(timeout=2)
                    )

                finally:
                    release.set()

                result = login_future.result(timeout=5)

                self.assertIn(
                    "session_token",
                    result
                )

    def test_concurrent_login_cannot_reuse_same_otp(self):
        self.auth.request_otp(self.password)

        code = self.read_otp()

        barrier = threading.Barrier(2)

        def attempt_login():
            barrier.wait(timeout=5)

            try:
                result = self.auth.login(code)

                return (
                    True,
                    result["session_token"]
                )

            except ValueError:
                return False, None

        with ThreadPoolExecutor(max_workers=2) as pool:

            first = pool.submit(attempt_login)
            second = pool.submit(attempt_login)

            results = [
                first.result(timeout=5),
                second.result(timeout=5)
            ]

        successful = [
            token
            for success, token in results
            if success
        ]

        failed = [
            success
            for success, token in results
            if not success
        ]

        self.assertEqual(len(successful), 1)
        self.assertEqual(len(failed), 1)

        self.assertTrue(
            self.auth.require_admin(successful[0])
        )

        self.assertFalse(
            self.mailbox.exists()
        )


if __name__ == "__main__":
    unittest.main()