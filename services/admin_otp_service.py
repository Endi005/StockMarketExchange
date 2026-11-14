
import hashlib
import hmac
import secrets
import threading
import time
from pathlib import Path


class AdminOTPService:

    def __init__(self, mailbox_path, ttl_seconds=120, clock=None):
        self._mailbox_path = Path(mailbox_path)
        self._ttl_seconds = ttl_seconds
        self._clock = clock if clock is not None else time.monotonic
        self._lock = threading.Lock()

        self._code_hash = None
        self._expires_at = 0

    def request_code(self):
        with self._lock:
            code = f"{secrets.randbelow(1000000):06d}"

            self._mailbox_path.parent.mkdir(
                parents=True, exist_ok=True
            )

            self._mailbox_path.write_text(
                f"Administrator one-time password: {code}\n",
                encoding="utf-8"
            )

            self._code_hash = hashlib.sha256(
                code.encode("utf-8")
            ).digest()

            self._expires_at = (
                self._clock() + self._ttl_seconds
            )

            return {
                "message": "OTP written to the simulated mailbox."
            }

    def verify_code(self, code):
        with self._lock:
            if self._code_hash is None:
                raise ValueError(
                    "No active OTP. Request a new code."
                )

            if self._clock() >= self._expires_at:
                self._code_hash = None
                raise ValueError(
                    "OTP expired. Request a new code."
                )

            if not isinstance(code, str):
                raise ValueError("Invalid OTP.")

            attempted_hash = hashlib.sha256(
                code.encode("utf-8")
            ).digest()

            if not hmac.compare_digest(
                attempted_hash, self._code_hash
            ):
                raise ValueError(
                    "Incorrect OTP. Check the mailbox."
                )

            self._code_hash = None
            self._expires_at = 0
            self._mailbox_path.unlink(missing_ok=True)

            return True
