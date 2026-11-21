
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from models.customer import CustomerAccount
from models.order import Order
from repositories.trading_repository import TradingRepository
from services.order_processor import OrderProcessor


class TestOrderProcessor(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.repository = TradingRepository(
            Path(self.directory.name) / "trading.json"
        )

        self.customer = CustomerAccount(
            "Frank", "password123"
        )

        self.repository.save(
            {"Frank": self.customer},
            {}
        )

        self.gateway = Mock()
        self.gateway.get_price.return_value = 20000

        self.processor = OrderProcessor(
            self.repository,
            self.gateway
        )

        self.order = Order(
            "Frank", "AAPL", "buy", 2
        )

    def test_submit_saves_pending_order(self):
        result = self.processor.submit(self.order)

        self.assertEqual(result["status"], "PENDING")

        customers, orders = self.repository.load()

        self.assertIn(self.order.order_id, orders)
        self.assertEqual(
            orders[self.order.order_id].status,
            "PENDING"
        )

    def test_successful_buy_order(self):
        self.processor.submit(self.order)

        result = self.processor.process(
            self.order.order_id
        )

        self.assertEqual(result["status"], "FILLED")

        customers, orders = self.repository.load()

        portfolio = customers["Frank"].get_portfolio()

        self.assertEqual(
            portfolio["cash_cents"],
            60000
        )
        self.assertEqual(
            portfolio["holdings"]["AAPL"]["shares"],
            2
        )
        self.assertEqual(
            orders[self.order.order_id].status,
            "FILLED"
        )

    def test_insufficient_funds_rejected(self):
        order = Order("Frank", "AAPL", "buy", 10)

        self.processor.submit(order)
        result = self.processor.process(order.order_id)

        self.assertEqual(result["status"], "REJECTED")

        customers, orders = self.repository.load()

        self.assertEqual(
            customers["Frank"].get_portfolio()["cash_cents"],
            100000
        )

    def test_duplicate_order_id_rejected(self):
        self.processor.submit(self.order)

        with self.assertRaises(ValueError):
            self.processor.submit(self.order)

    def test_cancel_pending_order(self):
        self.processor.submit(self.order)

        result = self.processor.cancel(
            self.order.order_id
        )

        self.assertEqual(result["status"], "CANCELLED")

        customers, orders = self.repository.load()

        self.assertEqual(
            orders[self.order.order_id].status,
            "CANCELLED"
        )

    def test_completed_order_not_executed_twice(self):
        self.processor.submit(self.order)

        first_result = self.processor.process(
            self.order.order_id
        )

        second_result = self.processor.process(
            self.order.order_id
        )

        self.assertEqual(first_result, second_result)

        customers, orders = self.repository.load()

        self.assertEqual(
            customers["Frank"].get_portfolio()["cash_cents"],
            60000
        )

        self.gateway.get_price.assert_called_once()

    def test_pending_order_survives_restart(self):
        self.processor.submit(self.order)

        restarted = OrderProcessor(
            self.repository,
            self.gateway
        )

        self.assertIn(
            self.order.order_id,
            restarted.pending_order_ids()
        )

        result = restarted.process(self.order.order_id)

        self.assertEqual(result["status"], "FILLED")

    def test_failed_save_preserves_pending_order(self):
        self.processor.submit(self.order)

        with patch.object(
            self.repository,
            "save",
            side_effect=OSError("Simulated disk failure")
        ):
            with self.assertRaises(OSError):
                self.processor.process(
                    self.order.order_id
                )

        customers, orders = self.repository.load()

        self.assertEqual(
            orders[self.order.order_id].status,
            "PENDING"
        )

        self.assertEqual(
            customers["Frank"].get_portfolio()["cash_cents"],
            100000
        )

    def test_gateway_failure_preserves_order(self):
        self.processor.submit(self.order)

        self.gateway.get_price.side_effect = (
            ConnectionError("Exchange unavailable")
        )

        with self.assertRaises(ConnectionError):
            self.processor.process(
                self.order.order_id
            )

        self.assertEqual(
            self.processor.get_order(
                self.order.order_id
            )["status"],
            "PENDING"
        )

    def test_unknown_customer_rejected(self):
        order = Order(
            "Unknown", "AAPL", "buy", 1
        )

        with self.assertRaises(ValueError):
            self.processor.submit(order)

    def test_pending_order_list(self):
        self.processor.submit(self.order)

        self.assertEqual(
            self.processor.pending_order_ids(),
            [self.order.order_id]
        )

        self.processor.process(self.order.order_id)

        self.assertEqual(
            self.processor.pending_order_ids(),
            []
        )


if __name__ == "__main__":
    unittest.main()
