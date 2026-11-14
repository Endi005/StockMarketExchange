
import hashlib
import hmac
import secrets
import threading
import time


class AdminAuthService:

    def __init__(
        self,
        otp_service,
        admin_password,
        session_ttl_seconds=900,
        clock=None
    ):
        if not isinstance(admin_password, str) or len(admin_password) < 8:
            raise ValueError(
                "Administrator password must have at least 8 characters."
            )

        self._otp_service = otp_service
        self._clock = clock if clock is not None else time.monotonic
        self._session_ttl = session_ttl_seconds
        self._lock = threading.RLock()
        self._sessions = {}

        self._salt = secrets.token_bytes(16)
        self._password_hash = self._hash_password(admin_password)

    def _hash_password(self, password):
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            self._salt,
            200000
        )

    def request_otp(self, password):
        if not isinstance(password, str):
            raise ValueError(
                "OTP refused: invalid administrator password."
            )

        attempted_hash = self._hash_password(password)

        with self._lock:
            if not hmac.compare_digest(
                attempted_hash, self._password_hash
            ):
                raise ValueError(
                    "OTP refused: incorrect administrator password. "
                    "Check your credentials."
                )

            return self._otp_service.request_code()

    def login(self, code):
        with self._lock:
            self._otp_service.verify_code(code)

            token = secrets.token_urlsafe(32)

            self._sessions[token] = (
                self._clock() + self._session_ttl
            )

            return {"session_token": token}

    def require_admin(self, token):
        with self._lock:
            if not isinstance(token, str):
                raise ValueError(
                    "Admin access refused. Log in again."
                )

            expires_at = self._sessions.get(token)

            if expires_at is None or self._clock() >= expires_at:
                self._sessions.pop(token, None)
                raise ValueError(
                    "Admin session invalid or expired. Log in again."
                )

            return True

    def logout(self, token):
        with self._lock:
            self.require_admin(token)
            del self._sessions[token]
            return True
