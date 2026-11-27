import io
import re
import secrets
import time
import json
import socket
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from clients.admin_client import AdminClient
from models.stock import Stock
from repositories.trading_repository import TradingRepository
from services.exchange_service import ExchangeService
from services.exchange_gateway import ExchangeGateway
from services.server_auth import sign_message, verify_message
from services.order_processor import OrderProcessor
from services.order_queue import OrderQueue
from services.queued_customer_service import QueuedCustomerService
from services.admin_auth_service import AdminAuthService
from services.admin_otp_service import AdminOTPService
from servers.exchange_server import ExchangeServer
from servers.broker_server import BrokerServer


class ServerIntegrationTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        key = "integration-test-secret-key"
        key_path = Path(self.temp_dir.name) / "server_key.txt"
        key_path.write_text(key, encoding="utf-8")

        exchange_service = ExchangeService([
            Stock("Apple", "AAPL", 20000),
            Stock("Tesla", "TSLA", 25000)
        ])

        self.exchange_server = ExchangeServer(
            ("127.0.0.1", 0),
            exchange_service,
            key
        )

        # Wait for active request threads during test cleanup.
        self.exchange_server.daemon_threads = False

        self.addCleanup(self.exchange_server.server_close)

        exchange_thread = threading.Thread(
            target=self.exchange_server.serve_forever,
            daemon=True
        )

        exchange_thread.start()
        self.addCleanup(exchange_thread.join)
        self.addCleanup(self.exchange_server.shutdown)

        self.gateway = ExchangeGateway(
            port=self.exchange_server.server_address[1]
        )

        self.gateway.key_file = key_path

        self.repository = TradingRepository(
            Path(self.temp_dir.name) / "trading.json"
        )

        processor = OrderProcessor(
            self.repository,
            self.gateway
        )

        self.order_queue = OrderQueue(processor)
        self.order_queue.start()
        self.addCleanup(self.order_queue.stop)

        customer_service = QueuedCustomerService(
            self.order_queue
        )

        # Real administrator authentication.

        self.admin_password = "IntegrationAdmin123!"

        self.mailbox_path = (
            Path(self.temp_dir.name) / "admin_mailbox.txt"
        )

        otp_service = AdminOTPService(
            self.mailbox_path
        )

        admin_auth = AdminAuthService(
            otp_service,
            self.admin_password
        )

        self.broker_server = BrokerServer(
            ("127.0.0.1", 0),
            customer_service,
            self.gateway,
            admin_auth
        )

        self.broker_server.daemon_threads = False

        self.addCleanup(self.broker_server.server_close)

        broker_thread = threading.Thread(
            target=self.broker_server.serve_forever,
            daemon=True
        )

        broker_thread.start()
        self.addCleanup(broker_thread.join)
        self.addCleanup(self.broker_server.shutdown)

    def send_broker_request(self, request):

        with socket.create_connection(
            self.broker_server.server_address,
            timeout=5
        ) as connection:

            connection.settimeout(5)

            with connection.makefile("rwb") as stream:

                stream.write(
                    (json.dumps(request) + "\n").encode("utf-8")
                )

                stream.flush()

                response = stream.readline(8192)

                # Wait until the handler finishes and closes
                # the connection, including performance recording.
                remaining = stream.read()

                self.assertEqual(remaining, b"")

        self.assertTrue(response.endswith(b"\n"))

        return json.loads(response.decode("utf-8"))

    def register_and_login(self, username):

        password = "SecurePass123!"

        registration = self.send_broker_request({
            "action": "register",
            "username": username,
            "password": password
        })

        self.assertTrue(registration["ok"], registration)

        login = self.send_broker_request({
            "action": "login",
            "username": username,
            "password": password
        })

        self.assertTrue(login["ok"], login)

        return login["data"]["session_token"]

    def login_as_admin(self):

        otp_response = self.send_broker_request({
            "action": "admin_request_otp",
            "admin_password": self.admin_password
        })

        self.assertTrue(otp_response["ok"], otp_response)

        mailbox_content = self.mailbox_path.read_text(
            encoding="utf-8"
        )

        code = mailbox_content.strip().rsplit(" ", 1)[-1]

        login_response = self.send_broker_request({
            "action": "admin_login",
            "otp": code
        })

        self.assertTrue(login_response["ok"], login_response)

        self.assertFalse(self.mailbox_path.exists())

        return login_response["data"]["session_token"]

    # Existing integration tests.

    def test_broker_gets_prices_from_real_exchange(self):

        token = self.register_and_login("IntegrationUser")

        prices = self.send_broker_request({
            "action": "get_prices",
            "session_token": token
        })

        self.assertTrue(prices["ok"], prices)
        self.assertEqual(prices["data"]["AAPL"], 20000)
        self.assertEqual(prices["data"]["TSLA"], 25000)

    def test_customer_can_submit_buy_order(self):

        token = self.register_and_login("TradingTestUser")

        buy_response = self.send_broker_request({
            "action": "buy",
            "session_token": token,
            "symbol": "AAPL",
            "quantity": 1
        })

        self.assertTrue(buy_response["ok"], buy_response)

        order_id = buy_response["data"]["order_id"]

        order_response = self.send_broker_request({
            "action": "get_order",
            "session_token": token,
            "order_id": order_id
        })

        self.assertTrue(order_response["ok"], order_response)

        self.assertEqual(
            order_response["data"]["order_id"],
            order_id
        )

        self.assertEqual(
            order_response["data"]["symbol"],
            "AAPL"
        )

    def test_completed_trade_survives_processor_restart(self):

        token = self.register_and_login("PersistenceUser")

        buy_response = self.send_broker_request({
            "action": "buy",
            "session_token": token,
            "symbol": "AAPL",
            "quantity": 1
        })

        self.assertTrue(buy_response["ok"], buy_response)

        order_id = buy_response["data"]["order_id"]

        self.order_queue.wait_until_idle()

        completed_response = self.send_broker_request({
            "action": "get_order",
            "session_token": token,
            "order_id": order_id
        })

        self.assertTrue(
            completed_response["ok"],
            completed_response
        )

        completed_order = completed_response["data"]

        self.assertEqual(
            completed_order["status"],
            "FILLED"
        )

        restarted_repository = TradingRepository(
            Path(self.temp_dir.name) / "trading.json"
        )

        restarted_processor = OrderProcessor(
            restarted_repository,
            self.gateway
        )

        restored_order = restarted_processor.get_order(
            order_id
        )

        self.assertEqual(
            restored_order["status"],
            "FILLED"
        )

        self.assertEqual(
            restored_order["order_id"],
            order_id
        )

        restored_portfolio = (
            restarted_processor.get_customer_portfolio(
                "PersistenceUser"
            )
        )

        self.assertEqual(
            restored_portfolio["holdings"]["AAPL"]["shares"],
            1
        )

    # Performance and security integration tests.

    def test_real_administrator_authentication(self):

        token = self.login_as_admin()

        response = self.send_broker_request({
            "action": "admin_status",
            "admin_token": token
        })

        self.assertTrue(response["ok"], response)

        self.assertTrue(
            response["data"]["administrator_authenticated"]
        )

    def test_successful_customer_requests_are_monitored(self):

        self.register_and_login("MonitoringUser")

        stats = (
            self.broker_server.performance_monitor
            .get_statistics()
        )

        self.assertEqual(stats["total_requests"], 2)
        self.assertEqual(stats["successful_requests"], 2)
        self.assertEqual(stats["failed_requests"], 0)

        self.assertEqual(
            stats["actions"]["register"]["successful"],
            1
        )

        self.assertEqual(
            stats["actions"]["login"]["successful"],
            1
        )

    def test_failed_customer_login_is_monitored(self):

        self.register_and_login("FailedLoginUser")

        response = self.send_broker_request({
            "action": "login",
            "username": "FailedLoginUser",
            "password": "WrongPassword123!"
        })

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "REQUEST_REJECTED"
        )

        stats = (
            self.broker_server.performance_monitor
            .get_statistics()
        )

        self.assertEqual(stats["total_requests"], 3)
        self.assertEqual(stats["successful_requests"], 2)
        self.assertEqual(stats["failed_requests"], 1)

        self.assertEqual(
            stats["actions"]["login"]["failed"],
            1
        )

    def test_both_servers_monitor_stock_price_request(self):

        token = self.register_and_login("PriceMonitorUser")

        response = self.send_broker_request({
            "action": "get_prices",
            "session_token": token
        })

        self.assertTrue(response["ok"], response)

        broker_stats = (
            self.broker_server.performance_monitor
            .get_statistics()
        )

        # Wait for active exchange handlers to finish.
        self.exchange_server.shutdown()
        self.exchange_server.server_close()

        exchange_stats = (
            self.exchange_server.performance_monitor
            .get_statistics()
        )

        self.assertEqual(
            broker_stats["actions"]["get_prices"]["successful"],
            1
        )

        self.assertEqual(
            exchange_stats["actions"]["get_prices"]["successful"],
            1
        )

    def test_admin_can_retrieve_broker_performance(self):

        self.register_and_login("BrokerStatsUser")

        admin_token = self.login_as_admin()

        response = self.send_broker_request({
            "action": "admin_statistics",
            "admin_token": admin_token
        })

        self.assertTrue(response["ok"], response)

        data = response["data"]

        self.assertEqual(data["customer_count"], 1)
        self.assertIn("performance", data)

        performance = data["performance"]

        self.assertGreaterEqual(
            performance["total_requests"],
            4
        )

        self.assertIn("average_duration_ms", performance)
        self.assertIn("requests_per_second", performance)
        self.assertIn("failure_rate_percent", performance)

    def test_admin_can_retrieve_exchange_performance(self):

        admin_token = self.login_as_admin()

        response = self.send_broker_request({
            "action": "admin_exchange_statistics",
            "admin_token": admin_token
        })

        self.assertTrue(response["ok"], response)

        data = response["data"]

        self.assertEqual(data["stock_count"], 2)
        self.assertIn("performance", data)

        performance = data["performance"]

        self.assertIn("total_requests", performance)
        self.assertIn("average_duration_ms", performance)
        self.assertIn("requests_per_second", performance)
        self.assertIn("actions", performance)

    def test_unauthorized_statistics_access_is_rejected(self):

        customer_token = self.register_and_login(
            "UnauthorizedUser"
        )

        for action in (
            "admin_statistics",
            "admin_exchange_statistics"
        ):

            with self.subTest(action=action):

                unauthenticated = self.send_broker_request({
                    "action": action
                })

                self.assertFalse(unauthenticated["ok"])
                self.assertNotIn("data", unauthenticated)

                customer_attempt = self.send_broker_request({
                    "action": action,
                    "session_token": customer_token,
                    "admin_token": customer_token
                })

                self.assertFalse(customer_attempt["ok"])
                self.assertNotIn("data", customer_attempt)

                self.assertEqual(
                    customer_attempt["error_code"],
                    "REQUEST_REJECTED"
                )

    def test_admin_client_displays_both_server_metrics(self):

        admin_token = self.login_as_admin()

        client = AdminClient()

        client.host = self.broker_server.server_address[0]
        client.port = self.broker_server.server_address[1]
        client.admin_token = admin_token

        output = io.StringIO()

        with redirect_stdout(output):
            client.show_statistics()
            client.show_exchange_statistics()

        displayed = output.getvalue()

        self.assertIn(
            "BROKER SERVER PERFORMANCE",
            displayed
        )

        self.assertIn(
            "EXCHANGE SERVER PERFORMANCE",
            displayed
        )

        self.assertIn("Total requests:", displayed)
        self.assertIn("Successful requests:", displayed)
        self.assertIn("Failed requests:", displayed)
        self.assertIn("Failure rate:", displayed)
        self.assertIn("Average request duration:", displayed)
        self.assertIn("Maximum request duration:", displayed)
        self.assertIn("Average throughput:", displayed)
        self.assertIn("Performance by operation:", displayed)

    # Correlation integration helpers.

    def correlation_ids(self, logs, action):

        pattern = (
            r"correlation_id=([0-9a-f]{32}) action="
            + re.escape(action)
            + r" success=True\b"
        )

        return re.findall(
            pattern,
            "\n".join(logs)
        )

    def finish_exchange_requests(self):

        self.exchange_server.shutdown()
        self.exchange_server.server_close()

    # Cross-server correlation integration tests.

    def test_synchronous_cross_server_correlation(self):

        token = self.register_and_login(
            "CorrelationUser"
        )

        with self.assertLogs(
            "broker", level="INFO"
        ) as broker_logs:

            with self.assertLogs(
                "exchange", level="INFO"
            ) as exchange_logs:

                response = self.send_broker_request({
                    "action": "get_prices",
                    "session_token": token
                })

                self.assertTrue(response["ok"], response)

                self.finish_exchange_requests()

        broker_ids = self.correlation_ids(
            broker_logs.output,
            "get_prices"
        )

        exchange_ids = self.correlation_ids(
            exchange_logs.output,
            "get_prices"
        )

        self.assertEqual(len(broker_ids), 1)
        self.assertEqual(broker_ids, exchange_ids)

    def verify_trade_correlation(self, side):

        token = self.register_and_login(
            "TradeCorrelationUser"
        )

        # A sell order requires an existing holding.
        if side == "sell":

            purchase = self.send_broker_request({
                "action": "buy",
                "session_token": token,
                "symbol": "AAPL",
                "quantity": 1
            })

            self.assertTrue(purchase["ok"], purchase)

            self.order_queue.wait_until_idle()

            self.assertEqual(
                self.order_queue.get_order(
                    purchase["data"]["order_id"]
                )["status"],
                "FILLED"
            )

        with self.assertLogs(
            "broker", level="INFO"
        ) as broker_logs:

            with self.assertLogs(
                "exchange", level="INFO"
            ) as exchange_logs:

                response = self.send_broker_request({
                    "action": side,
                    "session_token": token,
                    "symbol": "AAPL",
                    "quantity": 1
                })

                self.assertTrue(response["ok"], response)

                self.order_queue.wait_until_idle()

                order = self.order_queue.get_order(
                    response["data"]["order_id"]
                )

                self.finish_exchange_requests()

        self.assertEqual(
            order["status"],
            "FILLED"
        )

        broker_ids = self.correlation_ids(
            broker_logs.output,
            side
        )

        exchange_ids = self.correlation_ids(
            exchange_logs.output,
            "get_price"
        )

        self.assertEqual(
            broker_ids,
            [order["correlation_id"]]
        )

        self.assertEqual(
            exchange_ids,
            broker_ids
        )

        completed = [
            line
            for line in broker_logs.output
            if "Order execution completed:" in line
        ]

        self.assertEqual(len(completed), 1)

        self.assertIn(
            "correlation_id=" + order["correlation_id"],
            completed[0]
        )

        self.assertIn(
            "order_id=" + order["order_id"],
            completed[0]
        )

        self.assertIn(
            "status=FILLED",
            completed[0]
        )

    def test_asynchronous_buy_correlation(self):

        self.verify_trade_correlation("buy")

    def test_asynchronous_sell_correlation(self):

        self.verify_trade_correlation("sell")

    def test_separate_requests_have_distinct_correlation_ids(self):

        token = self.register_and_login(
            "IsolationUser"
        )

        with self.assertLogs(
            "broker", level="INFO"
        ) as broker_logs:

            with self.assertLogs(
                "exchange", level="INFO"
            ) as exchange_logs:

                for _ in range(2):

                    response = self.send_broker_request({
                        "action": "get_prices",
                        "session_token": token
                    })

                    self.assertTrue(
                        response["ok"],
                        response
                    )

                self.finish_exchange_requests()

        broker_ids = self.correlation_ids(
            broker_logs.output,
            "get_prices"
        )

        exchange_ids = self.correlation_ids(
            exchange_logs.output,
            "get_prices"
        )

        self.assertEqual(len(broker_ids), 2)
        self.assertEqual(len(set(broker_ids)), 2)

        self.assertCountEqual(
            broker_ids,
            exchange_ids
        )

    def test_customer_cannot_choose_correlation_id(self):

        token = self.register_and_login(
            "UntrustedCorrelationUser"
        )

        supplied = "f" * 32

        with self.assertLogs(
            "broker", level="INFO"
        ) as broker_logs:

            with self.assertLogs(
                "exchange", level="INFO"
            ) as exchange_logs:

                response = self.send_broker_request({
                    "action": "get_prices",
                    "session_token": token,
                    "correlation_id": supplied
                })

                self.assertTrue(response["ok"], response)

                self.finish_exchange_requests()

        broker_ids = self.correlation_ids(
            broker_logs.output,
            "get_prices"
        )

        self.assertEqual(len(broker_ids), 1)

        self.assertNotIn(
            supplied,
            broker_ids
        )

        self.assertEqual(
            broker_ids,
            self.correlation_ids(
                exchange_logs.output,
                "get_prices"
            )
        )

    def test_exchange_rejects_invalid_and_tampered_correlation(self):

        key = self.gateway.key_file.read_text(
            encoding="utf-8"
        ).strip()

        for tampered in (False, True):

            with self.subTest(tampered=tampered):

                request = {
                    "action": "get_prices",
                    "nonce": secrets.token_urlsafe(24),
                    "timestamp": time.time(),
                    "correlation_id": (
                        "a" * 32
                        if tampered
                        else "invalid"
                    )
                }

                request["signature"] = sign_message(
                    request,
                    key,
                    "broker-request"
                )

                if tampered:
                    request["correlation_id"] = "b" * 32

                with socket.create_connection(
                    self.exchange_server.server_address,
                    timeout=5
                ) as connection:

                    with connection.makefile("rwb") as stream:

                        stream.write(
                            (json.dumps(request) + "\n")
                            .encode("utf-8")
                        )

                        stream.flush()

                        response = json.loads(
                            stream.readline(8192)
                        )

                self.assertTrue(
                    verify_message(
                        response,
                        key,
                        "exchange-response"
                    )
                )

                self.assertFalse(response["ok"])

                self.assertEqual(
                    response["error_code"],
                    "REQUEST_REJECTED"
                )

                self.assertNotIn(
                    "data",
                    response
                )

                self.assertNotEqual(
                    response["correlation_id"],
                    request["correlation_id"]
                )


if __name__ == "__main__":
    unittest.main()