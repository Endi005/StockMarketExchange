
import unittest

from services.replay_guard import ReplayGuard


class TestReplayGuard(unittest.TestCase):

    def setUp(self):
        self.current_time = 1000

        self.guard = ReplayGuard(
            ttl_seconds=60,
            clock=lambda: self.current_time
        )

    def test_new_request_accepted(self):
        self.assertTrue(
            self.guard.accept("nonce-1", 1000)
        )

    def test_duplicate_request_rejected(self):
        self.guard.accept("nonce-1", 1000)

        self.assertFalse(
            self.guard.accept("nonce-1", 1000)
        )

    def test_different_nonces_accepted(self):
        self.assertTrue(
            self.guard.accept("nonce-1", 1000)
        )

        self.assertTrue(
            self.guard.accept("nonce-2", 1000)
        )

    def test_expired_request_rejected(self):
        self.assertFalse(
            self.guard.accept("nonce-old", 900)
        )

    def test_future_request_rejected(self):
        self.assertFalse(
            self.guard.accept("nonce-future", 1100)
        )

    def test_invalid_nonce_rejected(self):
        self.assertFalse(
            self.guard.accept("", 1000)
        )

        self.assertFalse(
            self.guard.accept(None, 1000)
        )

    def test_invalid_timestamp_rejected(self):
        self.assertFalse(
            self.guard.accept("nonce-1", "1000")
        )

        self.assertFalse(
            self.guard.accept("nonce-2", True)
        )

    def test_nonce_can_be_reused_after_expiry(self):
        self.assertTrue(
            self.guard.accept("nonce-1", 1000)
        )

        self.current_time = 1061

        self.assertTrue(
            self.guard.accept("nonce-1", 1061)
        )


if __name__ == "__main__":
    unittest.main()
