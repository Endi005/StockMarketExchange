import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from models.stock import Stock
from services.exchange_service import ExchangeService
from services.replay_guard import ReplayGuard
from services.server_auth import sign_message, verify_message
from services.performance_monitor import PerformanceMonitor
from servers.exchange_server import ExchangeHandler


class TestExchangeServerSecurity(unittest.TestCase):

    def setUp(self):
        self.secret = "test-secret-for-server-authentication"

        self.exchange = ExchangeService([
            Stock("Apple", "AAPL", 20000)
        ])

        self.server = SimpleNamespace(
            exchange=self.exchange,
            server_key=self.secret,
            replay_guard=ReplayGuard(
                ttl_seconds=300,
                clock=lambda: 1000
            ),
            performance_monitor=PerformanceMonitor()
        )

    def make_request(self, action="get_prices"):
        request = {
            "action": action,
            "nonce": "unique-test-request",
            "timestamp": 1000
        }

        request["signature"] = sign_message(
            request,
            self.secret,
            "broker-request"
        )

        return request

    def send_request(self, request):
        handler = ExchangeHandler.__new__(ExchangeHandler)

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

    def test_valid_signed_request(self):
        response = self.send_request(self.make_request())

        self.assertTrue(response["ok"])
        self.assertEqual(response["data"]["AAPL"], 20000)

    def test_response_is_signed(self):
        response = self.send_request(self.make_request())

        self.assertTrue(
            verify_message(
                response,
                self.secret,
                "exchange-response"
            )
        )

    def test_modified_request_rejected(self):
        request = self.make_request()
        request["action"] = "get_statistics"

        response = self.send_request(request)

        self.assertFalse(response["ok"])

    def test_replay_attack_rejected(self):
        request = self.make_request()

        first_response = self.send_request(request)
        second_response = self.send_request(request)

        self.assertTrue(first_response["ok"])
        self.assertFalse(second_response["ok"])

    def test_expired_request_rejected(self):
        request = self.make_request()
        request["timestamp"] = 500

        request["signature"] = sign_message(
            request,
            self.secret,
            "broker-request"
        )

        response = self.send_request(request)

        self.assertFalse(response["ok"])

    def test_valid_statistics_request(self):
        response = self.send_request(
            self.make_request("get_statistics")
        )

        self.assertTrue(response["ok"])
        self.assertEqual(
            response["data"]["stock_count"],
            1
        )

        self.assertIn("performance", response["data"])

        self.assertTrue(
            verify_message(
                response,
                self.secret,
                "exchange-response"
            )
        )

    def test_successful_request_is_monitored(self):
        response = self.send_request(self.make_request())

        self.assertTrue(response["ok"])

        stats = self.server.performance_monitor.get_statistics()

        self.assertEqual(stats["total_requests"], 1)
        self.assertEqual(stats["successful_requests"], 1)
        self.assertEqual(stats["failed_requests"], 0)

    def test_invalid_signature_is_monitored(self):
        request = self.make_request()
        request["signature"] = "invalid-signature"

        response = self.send_request(request)

        self.assertFalse(response["ok"])
        self.assertEqual(
            response["error_code"],
            "REQUEST_REJECTED"
        )

        stats = self.server.performance_monitor.get_statistics()

        self.assertEqual(stats["total_requests"], 1)
        self.assertEqual(stats["successful_requests"], 0)
        self.assertEqual(stats["failed_requests"], 1)

    def test_replay_failure_is_monitored(self):
        request = self.make_request()

        first_response = self.send_request(request)
        second_response = self.send_request(request)

        self.assertTrue(first_response["ok"])
        self.assertFalse(second_response["ok"])

        stats = self.server.performance_monitor.get_statistics()

        self.assertEqual(stats["total_requests"], 2)
        self.assertEqual(stats["successful_requests"], 1)
        self.assertEqual(stats["failed_requests"], 1)
        self.assertEqual(stats["failure_rate_percent"], 50.0)

    def test_statistics_requires_valid_signature(self):
        request = self.make_request("get_statistics")
        request["signature"] = "invalid-signature"

        response = self.send_request(request)

        self.assertFalse(response["ok"])
        self.assertNotIn("data", response)


if __name__ == "__main__":
    unittest.main()