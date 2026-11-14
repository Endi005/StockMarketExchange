
import threading
import time


class ReplayGuard:

    def __init__(self, ttl_seconds=300, clock=None):
        if ttl_seconds <= 0:
            raise ValueError("TTL must be positive.")

        self._ttl = ttl_seconds
        self._clock = clock if clock is not None else time.time
        self._used_nonces = {}
        self._lock = threading.Lock()

    def accept(self, nonce, timestamp):
        if not isinstance(nonce, str) or not nonce:
            return False

        if len(nonce) > 128:
            return False

        if type(timestamp) not in (int, float):
            return False

        now = self._clock()

        # Reject requests that are too old or too far
        # into the future.
        if not (-self._ttl < now - timestamp < self._ttl):
            return False

        with self._lock:
            # Remove nonces whose permitted time window
            # has already ended.
            self._used_nonces = {
                key: expires_at
                for key, expires_at in self._used_nonces.items()
                if expires_at > now
            }

            # Reject a nonce that was already used.
            if nonce in self._used_nonces:
                return False

            # Remember this nonce until its timestamp
            # is no longer valid.
            self._used_nonces[nonce] = timestamp + self._ttl

            return True
