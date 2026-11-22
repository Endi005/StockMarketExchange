
import hashlib
import hmac
import secrets
import threading
import time
from pathlib import Path


class AdminOTPService:

    MAX_ATTEMPTS = 6

    def __init__(self, mailbox_path, ttl_seconds=120, clock=None):
        self._mailbox_path = Path(mailbox_path)
        self._ttl_seconds = ttl_seconds
        self._clock = clock if clock is not None else time.monotonic
        self._lock = threading.Lock()

        self._code_hash = None
        self._expires_at = 0

        # Track incorrect verification attempts.
        self._failed_attempts = 0

    def _invalidate_code(self):
        """Invalidate the current OTP and delete its mailbox file."""

        self._code_hash = None
        self._expires_at = 0

        self._mailbox_path.unlink(missing_ok=True)

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

            # A newly issued OTP starts with zero failed attempts.
            self._failed_attempts = 0

            return {
                "message": "OTP written to the simulated mailbox."
            }

    def verify_code(self, code):
        with self._lock:

            # No OTP has been issued, or the previous one
            # has already been used or invalidated.
            if self._code_hash is None:
                raise ValueError(
                    "No active OTP. Request a new code."
                )

            # An expired OTP is no longer valid.
            if self._clock() >= self._expires_at:
                self._invalidate_code()

                raise ValueError(
                    "OTP expired. Request a new code."
                )

            # Invalid input also counts as a failed attempt.
            if not isinstance(code, str):
                self._failed_attempts += 1

                if self._failed_attempts >= self.MAX_ATTEMPTS:
                    self._invalidate_code()

                    raise ValueError(
                        "Too many incorrect OTP attempts. "
                        "Request a new code."
                    )

                raise ValueError("Invalid OTP.")

            attempted_hash = hashlib.sha256(
                code.encode("utf-8")
            ).digest()

            # Compare without using a regular == comparison.
            correct = hmac.compare_digest(
                attempted_hash,
                self._code_hash
            )

            if not correct:
                self._failed_attempts += 1

                # Invalidate the code after six failures.
                if self._failed_attempts >= self.MAX_ATTEMPTS:
                    self._invalidate_code()

                    raise ValueError(
                        "Too many incorrect OTP attempts. "
                        "Request a new code."
                    )

                raise ValueError(
                    "Incorrect OTP. Check the mailbox."
                )

            # Correct OTP: allow exactly one successful use.
            self._invalidate_code()
            self._failed_attempts = 0

            return True
