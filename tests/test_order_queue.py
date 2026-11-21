
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from models.customer import CustomerAccount
from models.order import Order
from repositories.trading_repository import TradingRepository
from services.order_processor import OrderProcessor
from services.order_queue import OrderQueue


class TestOrderQueue(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.repository = TradingRepository(
            Path(self.directory.name) / "trading.json"
        )

        customer = CustomerAccount(
            "Frank", "password123"
        )

        self.repository.save({"Frank": customer}, {})

        self.gateway = Mock()
        self.gateway.get_price.return_value = 20000

        self.processor = OrderProcessor(
            self.repository,
            self.gateway
        )

        self.queue = OrderQueue(self.processor)
        self.addCleanup(self.queue.stop)

    def test_order_is_processed(self):
        self.queue.start()

        order = Order("Frank", "AAPL", "buy", 2)
        self.queue.submit(order)
        self.queue.wait_until_idle()

        result = self.queue.get_order(order.order_id)

        self.assertEqual(result["status"], "FILLED")

        customers, orders = self.repository.load()

        self.assertEqual(
            customers["Frank"].get_portfolio()["cash_cents"],
            60000
        )

    def test_orders_are_processed_in_sequence(self):
        self.queue.start()

        first = Order("Frank", "AAPL", "buy", 3)
        second = Order("Frank", "AAPL", "buy", 3)

        self.queue.submit(first)
        self.queue.submit(second)
        self.queue.wait_until_idle()

        first_result = self.queue.get_order(first.order_id)
        second_result = self.queue.get_order(second.order_id)

        self.assertEqual(first_result["status"], "FILLED")
        self.assertEqual(second_result["status"], "REJECTED")

        customers, _ = self.repository.load()
        portfolio = customers["Frank"].get_portfolio()

        self.assertEqual(portfolio["cash_cents"], 40000)
        self.assertEqual(
            portfolio["holdings"]["AAPL"]["shares"],
            3
        )

    def test_pending_order_recovers_after_restart(self):
        order = Order("Frank", "AAPL", "buy", 2)

        self.processor.submit(order)

        restarted_processor = OrderProcessor(
            self.repository,
            self.gateway
        )

        recovered_queue = OrderQueue(restarted_processor)
        self.addCleanup(recovered_queue.stop)

        recovered_queue.start()
        recovered_queue.wait_until_idle()

        result = recovered_queue.get_order(order.order_id)

        self.assertEqual(result["status"], "FILLED")

    def test_completed_order_is_not_executed_twice(self):
        self.queue.start()

        order = Order("Frank", "AAPL", "buy", 2)

        self.queue.submit(order)
        self.queue.wait_until_idle()

        first_result = self.queue.get_order(order.order_id)

        self.assertEqual(first_result["status"], "FILLED")

        customers, _ = self.repository.load()

        self.assertEqual(
            customers["Frank"].get_portfolio()["cash_cents"],
            60000
        )

        self.gateway.get_price.assert_called_once()

    def test_duplicate_order_id_is_rejected(self):
        self.queue.start()

        order = Order("Frank", "AAPL", "buy", 2)

        self.queue.submit(order)

        with self.assertRaises(ValueError):
            self.queue.submit(order)

    def test_queue_rejects_requests_after_stop(self):
        self.queue.start()
        self.queue.stop()

        order = Order("Frank", "AAPL", "buy", 1)

        with self.assertRaises(RuntimeError):
            self.queue.submit(order)

    def test_unavailable_exchange_preserves_pending_order(self):
        self.gateway.get_price.side_effect = ConnectionError(
            "Exchange unavailable"
        )

        self.queue.start()

        order = Order("Frank", "AAPL", "buy", 2)

        self.queue.submit(order)
        self.queue.wait_until_idle()

        result = self.queue.get_order(order.order_id)

        self.assertEqual(result["status"], "PENDING")

        customers, orders = self.repository.load()

        self.assertEqual(
            customers["Frank"].get_portfolio()["cash_cents"],
            100000
        )
        self.assertEqual(
            orders[order.order_id].status,
            "PENDING"
        )


if __name__ == "__main__":
    unittest.main()
