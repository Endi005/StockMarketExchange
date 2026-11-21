
import unittest

from models.customer import CustomerAccount
from models.order import Order
from services.order_executor import OrderExecutor


class TestOrderExecutor(unittest.TestCase):

    def setUp(self):
        self.executor = OrderExecutor()

        self.customer = CustomerAccount(
            "Frank", "password123"
        )

        self.order = Order(
            "Frank", "AAPL", "buy", 2
        )

    def test_successful_buy(self):
        customer, order = self.executor.execute(
            self.order,
            self.customer,
            20000
        )

        portfolio = customer.get_portfolio()

        self.assertEqual(order.status, "FILLED")
        self.assertEqual(portfolio["cash_cents"], 60000)
        self.assertEqual(
            portfolio["holdings"]["AAPL"]["shares"],
            2
        )

    def test_successful_sell(self):
        self.customer.portfolio.buy(
            "AAPL", 2, 20000
        )

        sell_order = Order(
            "Frank", "AAPL", "sell", 1
        )

        customer, order = self.executor.execute(
            sell_order,
            self.customer,
            21000
        )

        portfolio = customer.get_portfolio()

        self.assertEqual(order.status, "FILLED")
        self.assertEqual(portfolio["cash_cents"], 81000)
        self.assertEqual(
            portfolio["holdings"]["AAPL"]["shares"],
            1
        )

    def test_insufficient_funds_rejects_order(self):
        expensive_order = Order(
            "Frank", "AAPL", "buy", 6
        )

        customer, order = self.executor.execute(
            expensive_order,
            self.customer,
            20000
        )

        self.assertEqual(order.status, "REJECTED")
        self.assertEqual(
            customer.get_portfolio()["cash_cents"],
            100000
        )

    def test_insufficient_shares_rejects_order(self):
        sell_order = Order(
            "Frank", "AAPL", "sell", 5
        )

        customer, order = self.executor.execute(
            sell_order,
            self.customer,
            20000
        )

        self.assertEqual(order.status, "REJECTED")
        self.assertEqual(
            customer.get_portfolio()["holdings"],
            {}
        )

    def test_original_customer_is_unchanged(self):
        self.executor.execute(
            self.order,
            self.customer,
            20000
        )

        original_portfolio = self.customer.get_portfolio()

        self.assertEqual(
            original_portfolio["cash_cents"],
            100000
        )
        self.assertEqual(
            original_portfolio["holdings"],
            {}
        )

    def test_original_order_is_unchanged(self):
        self.executor.execute(
            self.order,
            self.customer,
            20000
        )

        self.assertEqual(self.order.status, "PENDING")

    def test_wrong_customer_rejected(self):
        wrong_customer = CustomerAccount(
            "Emma", "password123"
        )

        with self.assertRaises(ValueError):
            self.executor.execute(
                self.order,
                wrong_customer,
                20000
            )

    def test_completed_order_cannot_execute_again(self):
        self.order.fill(
            20000,
            {
                "symbol": "AAPL",
                "shares": 2,
                "cost_cents": 40000
            }
        )

        with self.assertRaises(ValueError):
            self.executor.execute(
                self.order,
                self.customer,
                20000
            )

    def test_invalid_price_rejected(self):
        with self.assertRaises(ValueError):
            self.executor.execute(
                self.order,
                self.customer,
                -100
            )


if __name__ == "__main__":
    unittest.main()
