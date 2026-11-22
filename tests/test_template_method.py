
import unittest
from unittest.mock import Mock, patch

from services.base_request_handler import BaseRequestHandler


class TestTemplateMethod(unittest.TestCase):

    def test_shared_workflow(self):
        class TestHandler(BaseRequestHandler):
            safe_actions = frozenset({"get_prices"})
            logger = Mock()

            def _validate_request(self, request):
                self.steps.append("validate")

            def _process_request(self, request):
                self.steps.append("process")
                return {"AAPL": 20000}

            def _prepare_response(self, request, response):
                self.steps.append("prepare")
                return response

            def _handle_error(self, error, action_for_log):
                return {
                    "ok": False,
                    "error": str(error)
                }

        handler = object.__new__(TestHandler)
        handler.steps = []
        handler.wfile = Mock()

        with patch.object(
            TestHandler,
            "_read_request",
            return_value={"action": "get_prices"}
        ):
            handler.handle()

        self.assertEqual(
            handler.steps,
            ["validate", "process", "prepare"]
        )

        handler.wfile.write.assert_called_once()

    def test_exchange_rejects_invalid_signature(self):
        from servers.exchange_server import ExchangeHandler

        handler = object.__new__(ExchangeHandler)

        handler.server = Mock()
        handler.server.server_key = "test-secret-key"

        request = {
            "action": "get_prices",
            "nonce": "test-nonce",
            "timestamp": 123456789,
            "signature": "invalid-signature"
        }

        with self.assertRaises(ValueError):
            handler._validate_request(request)

        handler.server.replay_guard.accept.assert_not_called()


    def test_exchange_rejects_replayed_request(self):
        from servers.exchange_server import ExchangeHandler

        handler = object.__new__(ExchangeHandler)
        handler.server = Mock()
        handler.server.server_key = "test-secret-key"
        handler.server.replay_guard.accept.return_value = False

        request = {
            "action": "get_prices",
            "nonce": "repeated-nonce",
            "timestamp": 123456789
        }

        with patch(
            "servers.exchange_server.verify_message",
            return_value=True
        ):
            with self.assertRaisesRegex(
                ValueError,
                "Duplicate or expired server request"
            ):
                handler._validate_request(request)

        handler.server.replay_guard.accept.assert_called_once_with(
            "repeated-nonce",
            123456789
        )


    def test_exchange_response_is_signed(self):
        from servers.exchange_server import ExchangeHandler
        from services.server_auth import verify_message

        handler = object.__new__(ExchangeHandler)
        handler.server = Mock()
        handler.server.server_key = "test-secret-key"

        request = {
            "action": "get_prices",
            "nonce": "unique-test-nonce"
        }

        response = {
            "ok": True,
            "data": {"AAPL": 20000}
        }

        signed_response = handler._prepare_response(
            request,
            response
        )

        self.assertEqual(
            signed_response["nonce"],
            "unique-test-nonce"
        )

        self.assertIn(
            "signature",
            signed_response
        )

        self.assertTrue(
            verify_message(
                signed_response,
                "test-secret-key",
                "exchange-response"
            )
        )


if __name__ == "__main__":
    unittest.main()
