
import tempfile
import unittest
from pathlib import Path

from repositories.customer_repository import CustomerRepository
from services.customer_service import CustomerService


class FakeExchangeGateway:

    def get_price(self, symbol):
        prices = {"AAPL": 20000, "TSLA": 25000}
        return prices[symbol]


class TestCustomerTrading(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.path = Path(self.directory.name) / "customers.json"
        self.repository = CustomerRepository(self.path)

        self.service = CustomerService(
            self.repository,
            FakeExchangeGateway()
        )

        self.service.register("John", "password123")
        self.service.register("Emma", "password456")

        self.john_token = self.service.login(
            "John", "password123"
        )
        self.emma_token = self.service.login(
            "Emma", "password456"
        )

    def test_customers_have_separate_portfolios(self):
        self.service.buy_stock(
            self.john_token, "AAPL", 2
        )

        john = self.service.get_portfolio(self.john_token)
        emma = self.service.get_portfolio(self.emma_token)

        self.assertEqual(john["cash_cents"], 60000)
        self.assertEqual(emma["cash_cents"], 100000)
        self.assertEqual(emma["holdings"], {})

    def test_buy_and_sell(self):
        self.service.buy_stock(
            self.john_token, "AAPL", 2
        )
        self.service.sell_stock(
            self.john_token, "AAPL", 1
        )

        result = self.service.get_portfolio(
            self.john_token
        )

        self.assertEqual(result["cash_cents"], 80000)
        self.assertEqual(
            result["holdings"]["AAPL"]["shares"], 1
        )

    def test_accounts_survive_restart(self):
        self.service.buy_stock(
            self.john_token, "AAPL", 2
        )

        restarted = CustomerService(
            self.repository,
            FakeExchangeGateway()
        )

        new_token = restarted.login(
            "John", "password123"
        )

        result = restarted.get_portfolio(new_token)

        self.assertEqual(result["cash_cents"], 60000)
        self.assertEqual(
            result["holdings"]["AAPL"]["shares"], 2
        )

    def test_invalid_session_rejected(self):
        with self.assertRaises(ValueError):
            self.service.get_portfolio("invalid-token")

    def test_failed_purchase_does_not_change_balance(self):
        with self.assertRaises(ValueError):
            self.service.buy_stock(
                self.john_token, "AAPL", 100
            )

        result = self.service.get_portfolio(
            self.john_token
        )

        self.assertEqual(result["cash_cents"], 100000)


if __name__ == "__main__":
    unittest.main()
