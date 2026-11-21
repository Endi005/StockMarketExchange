
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from models.customer import CustomerAccount
from models.order import Order
from repositories.trading_repository import TradingRepository


class TestTradingRepository(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.path = Path(self.directory.name) / "trading.json"
        self.repository = TradingRepository(self.path)

        self.customer = CustomerAccount(
            "Frank", "password123"
        )
        self.customers = {"Frank": self.customer}

        self.order = Order(
            "Frank", "AAPL", "buy", 2
        )
        self.orders = {
            self.order.order_id: self.order
        }

    def test_empty_repository(self):
        customers, orders = self.repository.load()

        self.assertEqual(customers, {})
        self.assertEqual(orders, {})

    def test_save_and_load_pending_order(self):
        self.repository.save(self.customers, self.orders)

        customers, orders = self.repository.load()

        self.assertIn("Frank", customers)
        self.assertIn(self.order.order_id, orders)
        self.assertEqual(
            orders[self.order.order_id].status,
            "PENDING"
        )

    def test_save_and_load_filled_order(self):
        self.order.fill(
            20000,
            {
                "symbol": "AAPL",
                "shares": 2,
                "cost_cents": 40000
            }
        )

        self.repository.save(self.customers, self.orders)
        customers, orders = self.repository.load()

        restored = orders[self.order.order_id]

        self.assertEqual(restored.status, "FILLED")
        self.assertEqual(
            restored.to_record(),
            self.order.to_record()
        )

    def test_customer_portfolio_survives_restart(self):
        self.customer.portfolio.buy("AAPL", 2, 20000)
        self.order.fill(
            20000,
            {
                "symbol": "AAPL",
                "shares": 2,
                "cost_cents": 40000
            }
        )

        self.repository.save(self.customers, self.orders)
        customers, orders = TradingRepository(self.path).load()

        portfolio = customers["Frank"].get_portfolio()

        self.assertEqual(portfolio["cash_cents"], 60000)
        self.assertEqual(
            portfolio["holdings"]["AAPL"]["shares"],
            2
        )
        self.assertEqual(
            orders[self.order.order_id].status,
            "FILLED"
        )

    def test_unknown_customer_order_rejected(self):
        invalid_order = Order("Emma", "AAPL", "buy", 1)

        with self.assertRaises(ValueError):
            self.repository.save(
                self.customers,
                {invalid_order.order_id: invalid_order}
            )

    def test_corrupted_json_rejected(self):
        self.path.write_text(
            "{invalid json",
            encoding="utf-8"
        )

        with self.assertRaises(ValueError):
            self.repository.load()

    def test_corrupted_order_rejected(self):
        self.repository.save(self.customers, self.orders)

        data = json.loads(
            self.path.read_text(encoding="utf-8")
        )

        data["orders"][self.order.order_id]["status"] = "INVALID"

        self.path.write_text(
            json.dumps(data),
            encoding="utf-8"
        )

        with self.assertRaises(ValueError):
            self.repository.load()

    def test_failed_replacement_preserves_previous_data(self):
        self.repository.save(self.customers, self.orders)

        original = self.path.read_bytes()

        second_order = Order(
            "Frank", "TSLA", "buy", 1
        )

        updated_orders = dict(self.orders)
        updated_orders[second_order.order_id] = second_order

        with patch(
            "repositories.trading_repository.os.replace",
            side_effect=OSError("Simulated disk failure")
        ):
            with self.assertRaises(OSError):
                self.repository.save(
                    self.customers,
                    updated_orders
                )

        self.assertEqual(self.path.read_bytes(), original)

        customers, orders = self.repository.load()
        self.assertIn("Frank", customers)
        self.assertNotIn(second_order.order_id, orders)


if __name__ == "__main__":
    unittest.main()
