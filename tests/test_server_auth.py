
import unittest

from services.server_auth import (
    sign_message,
    verify_message
)


class TestServerAuth(unittest.TestCase):

    def setUp(self):
        self.secret = "test-server-secret"
        self.message = {
            "action": "get_prices",
            "nonce": "unique-request-123"
        }

    def test_valid_signature(self):
        signed = dict(self.message)
        signed["signature"] = sign_message(
            signed, self.secret, "broker-request"
        )

        self.assertTrue(
            verify_message(
                signed, self.secret, "broker-request"
            )
        )

    def test_modified_message_rejected(self):
        signed = dict(self.message)
        signed["signature"] = sign_message(
            signed, self.secret, "broker-request"
        )

        signed["action"] = "get_statistics"

        self.assertFalse(
            verify_message(
                signed, self.secret, "broker-request"
            )
        )

    def test_wrong_secret_rejected(self):
        signed = dict(self.message)
        signed["signature"] = sign_message(
            signed, self.secret, "broker-request"
        )

        self.assertFalse(
            verify_message(
                signed, "wrong-secret", "broker-request"
            )
        )

    def test_missing_signature_rejected(self):
        self.assertFalse(
            verify_message(
                self.message, self.secret, "broker-request"
            )
        )

    def test_wrong_purpose_rejected(self):
        signed = dict(self.message)
        signed["signature"] = sign_message(
            signed, self.secret, "broker-request"
        )

        self.assertFalse(
            verify_message(
                signed, self.secret, "exchange-response"
            )
        )

    def test_non_dictionary_rejected(self):
        self.assertFalse(
            verify_message(
                "invalid message",
                self.secret,
                "broker-request"
            )
        )


if __name__ == "__main__":
    unittest.main()
