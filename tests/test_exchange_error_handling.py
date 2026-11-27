import io
import json
import unittest

from types import SimpleNamespace
from unittest.mock import Mock, patch

from servers.exchange_server import (
    ExchangeHandler,
    automatic_price_updates
)

from services.server_auth import (
    sign_message,
    verify_message
)

from services.replay_guard import ReplayGuard
from services.performance_monitor import PerformanceMonitor


class TestExchangeErrorHandling(unittest.TestCase):

    def setUp(self):

        self.secret = "test-server-secret"
        self.correlation_id = "a" * 32

        self.exchange = Mock()

        self.server = SimpleNamespace(
            exchange=self.exchange,
            server_key=self.secret,
            replay_guard=ReplayGuard(
                ttl_seconds=300,
                clock=lambda: 1000
            ),
            performance_monitor=PerformanceMonitor()
        )

    def make_request(self):

        request = {
            "action": "get_prices",
            "nonce": "test-error-request",
            "timestamp": 1000,
            "correlation_id": self.correlation_id
        }

        request["signature"] = sign_message(
            request,
            self.secret,
            "broker-request"
        )

        return request

    def send_request(self, request):

        handler = object.__new__(ExchangeHandler)

        handler.server = self.server
        handler.request = Mock()

        handler.rfile = io.BytesIO(
            (json.dumps(request) + "\n").encode("utf-8")
        )

        handler.wfile = io.BytesIO()

        handler.handle()

        return json.loads(
            handler.wfile.getvalue().decode("utf-8")
        )

    def simulate_failure(self, error):

        self.exchange.get_prices.side_effect = error

        return self.send_request(
            self.make_request()
        )

    def test_runtime_error_is_hidden(self):

        response = self.simulate_failure(
            RuntimeError("Private internal information")
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "INTERNAL_ERROR"
        )

        self.assertNotIn(
            "Private internal information",
            response["error"]
        )

        self.assertNotIn("data", response)

    def test_type_error_is_hidden(self):

        response = self.simulate_failure(
            TypeError("Private programming information")
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "INTERNAL_ERROR"
        )

        self.assertNotIn(
            "Private programming information",
            response["error"]
        )

    def test_filesystem_error_is_hidden(self):

        response = self.simulate_failure(
            OSError("Private database file location")
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "INTERNAL_ERROR"
        )

        self.assertNotIn(
            "Private database file location",
            response["error"]
        )

    def test_connection_error(self):

        response = self.simulate_failure(
            ConnectionError("Private connection details")
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "COMMUNICATION_ERROR"
        )

        self.assertNotIn(
            "Private connection details",
            response["error"]
        )

    def test_timeout_error(self):

        response = self.simulate_failure(
            TimeoutError("Private timeout details")
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "COMMUNICATION_ERROR"
        )

    def test_validation_error_preserves_message(self):

        response = self.simulate_failure(
            ValueError("Invalid stock symbol.")
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "REQUEST_REJECTED"
        )

        self.assertEqual(
            response["error"],
            "Invalid stock symbol."
        )

    def test_unicode_error_returns_safe_message(self):

        error = UnicodeDecodeError(
            "utf-8",
            b"\xff",
            0,
            1,
            "invalid start byte"
        )

        response = self.simulate_failure(error)

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "REQUEST_REJECTED"
        )

        self.assertEqual(
            response["error"],
            "Invalid request encoding. Send UTF-8 JSON."
        )

    def test_error_response_is_authenticated(self):

        response = self.simulate_failure(
            RuntimeError("Internal failure")
        )

        self.assertTrue(
            verify_message(
                response,
                self.secret,
                "exchange-response"
            )
        )

        self.assertEqual(
            response["nonce"],
            "test-error-request"
        )

        self.assertEqual(
            response["correlation_id"],
            self.correlation_id
        )

    def test_modified_error_response_fails_authentication(self):

        response = self.simulate_failure(
            RuntimeError("Internal failure")
        )

        response["error_code"] = "MODIFIED_ERROR"

        self.assertFalse(
            verify_message(
                response,
                self.secret,
                "exchange-response"
            )
        )

    def test_internal_failure_logs_safe_diagnostics(self):

        def failing_operation():

            raise RuntimeError(
                "Sensitive internal diagnostic"
            )

        self.exchange.get_prices.side_effect = (
            failing_operation
        )

        with self.assertLogs(
            "exchange",
            level="ERROR"
        ) as captured:

            response = self.send_request(
                self.make_request()
            )

        output = "\n".join(captured.output)

        self.assertEqual(
            response["error_code"],
            "INTERNAL_ERROR"
        )

        self.assertIn(
            "correlation_id=" + self.correlation_id,
            output
        )

        self.assertIn(
            "error_type=RuntimeError",
            output
        )

        self.assertIn(
            "test_exchange_error_handling.py",
            output
        )

        self.assertIn(
            "failing_operation",
            output
        )

        self.assertNotIn(
            "Sensitive internal diagnostic",
            output
        )

    def test_internal_failure_is_monitored(self):

        response = self.simulate_failure(
            RuntimeError("Internal failure")
        )

        self.assertFalse(response["ok"])

        statistics = (
            self.server.performance_monitor.get_statistics()
        )

        self.assertEqual(
            statistics["total_requests"],
            1
        )

        self.assertEqual(
            statistics["failed_requests"],
            1
        )

        self.assertEqual(
            statistics["successful_requests"],
            0
        )

    def test_automatic_update_recovers_after_failure(self):

        exchange = Mock()

        exchange.simulate_tick.side_effect = [
            RuntimeError("Private update failure"),
            {"AAPL": 20100}
        ]

        stop_event = Mock()

        stop_event.wait.side_effect = [
            False,
            False,
            True
        ]

        with self.assertLogs(
            "exchange",
            level="INFO"
        ) as captured:

            with patch("builtins.print") as mock_print:

                automatic_price_updates(
                    exchange,
                    stop_event
                )

        self.assertEqual(
            exchange.simulate_tick.call_count,
            2
        )

        self.assertEqual(
            stop_event.wait.call_count,
            3
        )

        output = "\n".join(captured.output)

        self.assertIn(
            "Unexpected automatic price update failure",
            output
        )

        self.assertIn(
            "Automatic stock price update completed",
            output
        )

        self.assertNotIn(
            "Private update failure",
            output
        )

        self.assertNotIn(
            "Private update failure",
            str(mock_print.call_args_list)
        )


if __name__ == "__main__":
    unittest.main()