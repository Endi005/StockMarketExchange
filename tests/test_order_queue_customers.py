
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from models.customer import CustomerAccount
from models.order import Order
from repositories.trading_repository import TradingRepository
from services.order_processor import OrderProcessor
from services.order_queue import OrderQueue


class TestOrderQueueCustomers(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.repository = TradingRepository(
            Path(self.directory.name) / "trading.json"
        )

        frank = CustomerAccount("Frank", "password123")
        self.repository.save({"Frank": frank}, {})

        self.gateway = Mock()
        self.gateway.get_price.return_value = 20000

        self.processor = OrderProcessor(
            self.repository,
            self.gateway
        )

        self.queue = OrderQueue(self.processor)
        self.addCleanup(self.queue.stop)
        self.queue.start()

    def test_register_customer(self):
        result = self.queue.register_customer(
            "Emma", "password456"
        )

        self.assertEqual(result["username"], "Emma")

        customers, orders = self.repository.load()

        self.assertIn("Emma", customers)
        self.assertEqual(orders, {})

    def test_customer_login(self):
        username = self.queue.authenticate_customer(
            "Frank", "password123"
        )

        self.assertEqual(username, "Frank")

    def test_wrong_password_rejected(self):
        with self.assertRaises(ValueError):
            self.queue.authenticate_customer(
                "Frank", "wrongpassword"
            )

    def test_duplicate_registration_rejected(self):
        with self.assertRaises(ValueError):
            self.queue.register_customer(
                "Frank", "newpassword"
            )

        # Existing credentials must remain valid.
        result = self.queue.authenticate_customer(
            "Frank", "password123"
        )

        self.assertEqual(result, "Frank")

    def test_get_customer_portfolio(self):
        portfolio = self.queue.get_customer_portfolio(
            "Frank"
        )

        self.assertEqual(
            portfolio["cash_cents"], 100000
        )
        self.assertEqual(
            portfolio["holdings"], {}
        )

    def test_get_statistics(self):
        self.queue.register_customer(
            "Emma", "password456"
        )

        statistics = self.queue.get_statistics()

        self.assertEqual(
            statistics["customer_count"], 2
        )
        self.assertEqual(
            statistics["total_cash_cents"], 200000
        )
        self.assertEqual(
            statistics["total_shares"], 0
        )

    def test_customer_survives_restart(self):
        self.queue.register_customer(
            "Emma", "password456"
        )

        self.queue.stop()

        restarted_processor = OrderProcessor(
            self.repository,
            self.gateway
        )

        restarted_queue = OrderQueue(restarted_processor)
        self.addCleanup(restarted_queue.stop)

        restarted_queue.start()

        username = restarted_queue.authenticate_customer(
            "Emma", "password456"
        )

        self.assertEqual(username, "Emma")

    def test_registered_customer_can_buy_stock(self):
        self.queue.register_customer(
            "Emma", "password456"
        )

        order = Order("Emma", "AAPL", "buy", 1)

        self.queue.submit(order)
        self.queue.wait_until_idle()

        result = self.queue.get_order(order.order_id)

        self.assertEqual(result["status"], "FILLED")

        emma_portfolio = self.queue.get_customer_portfolio(
            "Emma"
        )

        frank_portfolio = self.queue.get_customer_portfolio(
            "Frank"
        )

        self.assertEqual(
            emma_portfolio["cash_cents"], 80000
        )
        self.assertEqual(
            frank_portfolio["cash_cents"], 100000
        )

        statistics = self.queue.get_statistics()

        self.assertEqual(
            statistics["total_shares"], 1
        )


if __name__ == "__main__":
    unittest.main()
