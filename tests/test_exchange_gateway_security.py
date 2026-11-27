import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.exchange_gateway import ExchangeGateway
from services.server_auth import sign_message, verify_message

from services.correlation_context import (
    correlation_scope,
    get_correlation_id,
    validate_correlation_id
)


class FakeStream:
    def __init__(self, response):
        self.response = response
        self.written = b""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def write(self, data):
        self.written += data

    def flush(self):
        pass

    def readline(self, size=8192):
        return self.response


class FakeConnection:
    def __init__(self, stream):
        self.stream = stream

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def settimeout(self, seconds):
        pass

    def makefile(self, mode):
        return self.stream


class TestExchangeGatewaySecurity(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

        self.secret = "test-server-secret"
        self.correlation_id = "a" * 32

        self.gateway = ExchangeGateway()

        self.gateway.key_file = (
            Path(self.folder.name) / "server_key.txt"
        )

        self.gateway.key_file.write_text(
            self.secret,
            encoding="utf-8"
        )

    def make_response(
        self,
        nonce="test-nonce",
        correlation_id=None
    ):

        if correlation_id is None:
            correlation_id = self.correlation_id

        response = {
            "ok": True,
            "data": {"AAPL": 20000},
            "nonce": nonce,
            "correlation_id": correlation_id
        }

        response["signature"] = sign_message(
            response,
            self.secret,
            "exchange-response"
        )

        return response

    def call_gateway(self, response):

        stream = FakeStream(
            (json.dumps(response) + "\n").encode("utf-8")
        )

        connection = FakeConnection(stream)

        with patch(
            "services.exchange_gateway.socket.create_connection",
            return_value=connection
        ), patch(
            "services.exchange_gateway.secrets.token_urlsafe",
            return_value="test-nonce"
        ), patch(
            "services.exchange_gateway.generate_correlation_id",
            return_value=self.correlation_id
        ):
            result = self.gateway.get_prices()

        return result, stream

    def test_valid_signed_response(self):

        result, stream = self.call_gateway(
            self.make_response()
        )

        self.assertEqual(result["AAPL"], 20000)

        sent_request = json.loads(
            stream.written.decode("utf-8")
        )

        self.assertTrue(
            verify_message(
                sent_request,
                self.secret,
                "broker-request"
            )
        )

    def test_modified_response_rejected(self):

        response = self.make_response()
        response["data"]["AAPL"] = 50000

        with self.assertRaises(RuntimeError):
            self.call_gateway(response)

    def test_wrong_signature_rejected(self):

        response = self.make_response()
        response["signature"] = "invalid-signature"

        with self.assertRaises(RuntimeError):
            self.call_gateway(response)

    def test_wrong_nonce_rejected(self):

        response = self.make_response(
            nonce="different-nonce"
        )

        with self.assertRaises(RuntimeError):
            self.call_gateway(response)

    def test_signed_error_response(self):

        response = {
            "ok": False,
            "error": "Stock unavailable",
            "nonce": "test-nonce",
            "correlation_id": "c" * 32
        }

        response["signature"] = sign_message(
            response,
            self.secret,
            "exchange-response"
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "Stock unavailable"
        ):
            self.call_gateway(response)

    def test_existing_correlation_id_propagated(self):

        existing_id = "b" * 32

        response = self.make_response(
            correlation_id=existing_id
        )

        with correlation_scope(existing_id):

            result, stream = self.call_gateway(response)

            self.assertEqual(
                get_correlation_id(),
                existing_id
            )

        sent_request = json.loads(
            stream.written.decode("utf-8")
        )

        self.assertEqual(
            sent_request["correlation_id"],
            existing_id
        )

        self.assertEqual(result["AAPL"], 20000)

        self.assertTrue(
            verify_message(
                sent_request,
                self.secret,
                "broker-request"
            )
        )

    def test_correlation_id_generated_without_context(self):

        self.assertIsNone(get_correlation_id())

        result, stream = self.call_gateway(
            self.make_response()
        )

        sent_request = json.loads(
            stream.written.decode("utf-8")
        )

        self.assertEqual(
            sent_request["correlation_id"],
            self.correlation_id
        )

        self.assertEqual(
            validate_correlation_id(
                sent_request["correlation_id"]
            ),
            self.correlation_id
        )

        self.assertIsNone(get_correlation_id())

    def test_wrong_signed_correlation_id_rejected(self):

        response = self.make_response(
            correlation_id="b" * 32
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "correlation ID mismatch"
        ):
            self.call_gateway(response)

    def test_missing_correlation_id_rejected(self):

        response = self.make_response()

        del response["correlation_id"]
        del response["signature"]

        response["signature"] = sign_message(
            response,
            self.secret,
            "exchange-response"
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "correlation ID mismatch"
        ):
            self.call_gateway(response)

    def test_tampered_correlation_id_rejected(self):

        response = self.make_response()

        # Modify the correlation ID after signing.
        response["correlation_id"] = "b" * 32

        with self.assertRaisesRegex(
            RuntimeError,
            "response authentication failed"
        ):
            self.call_gateway(response)


if __name__ == "__main__":
    unittest.main()