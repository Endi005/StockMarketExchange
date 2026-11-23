
import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path

from models.stock import Stock
from repositories.trading_repository import TradingRepository
from services.exchange_service import ExchangeService
from services.exchange_gateway import ExchangeGateway
from services.order_processor import OrderProcessor
from services.order_queue import OrderQueue
from services.queued_customer_service import QueuedCustomerService
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

        self.addCleanup(
            self.exchange_server.server_close
        )

        exchange_thread = threading.Thread(
            target=self.exchange_server.serve_forever,
            daemon=True
        )
        exchange_thread.start()

        self.addCleanup(
            self.exchange_server.shutdown
        )

        gateway = ExchangeGateway(
            port=self.exchange_server.server_address[1]
        )
        gateway.key_file = key_path

        repository = TradingRepository(
            Path(self.temp_dir.name) / "trading.json"
        )

        processor = OrderProcessor(repository, gateway)
        self.order_queue = OrderQueue(processor)
        self.order_queue.start()
        self.addCleanup(self.order_queue.stop)

        customer_service = QueuedCustomerService(
            self.order_queue
        )

        self.broker_server = BrokerServer(
            ("127.0.0.1", 0),
            customer_service,
            gateway,
            object()
        )

        self.addCleanup(
            self.broker_server.server_close
        )

        broker_thread = threading.Thread(
            target=self.broker_server.serve_forever,
            daemon=True
        )
        broker_thread.start()

        self.addCleanup(
            self.broker_server.shutdown
        )

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

        self.assertTrue(response.endswith(b"\n"))
        return json.loads(response.decode("utf-8"))

    def test_broker_gets_prices_from_real_exchange(self):
        registration = self.send_broker_request({
            "action": "register",
            "username": "IntegrationUser",
            "password": "SecurePass123!"
        })
        self.assertTrue(registration["ok"], registration)

        login = self.send_broker_request({
            "action": "login",
            "username": "IntegrationUser",
            "password": "SecurePass123!"
        })
        self.assertTrue(login["ok"], login)

        token = login["data"]["session_token"]

        prices = self.send_broker_request({
            "action": "get_prices",
            "session_token": token
        })

        self.assertTrue(prices["ok"], prices)
        self.assertEqual(
            prices["data"]["AAPL"],
            20000
        )
        self.assertEqual(
            prices["data"]["TSLA"],
            25000
        )

    def test_customer_can_submit_buy_order(self):
        username = "TradingTestUser"
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

        token = login["data"]["session_token"]

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


if __name__ == "__main__":
    unittest.main()
