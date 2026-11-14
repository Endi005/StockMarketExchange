
import unittest

from services.broker_service import BrokerService


class FakeExchangeGateway:

    def get_price(self, symbol):
        prices = {"AAPL": 20000, "TSLA": 25000}
        return prices[symbol]


class TestBrokerService(unittest.TestCase):

    def setUp(self):
        self.broker = BrokerService(FakeExchangeGateway())

    def test_buy_stock(self):
        self.broker.buy_stock("AAPL", 2)

        summary = self.broker.get_portfolio()

        self.assertEqual(summary["cash_cents"], 60000)
        self.assertEqual(
            summary["holdings"]["AAPL"]["shares"], 2
        )

    def test_sell_stock(self):
        self.broker.buy_stock("AAPL", 2)
        self.broker.sell_stock("AAPL", 1)

        summary = self.broker.get_portfolio()

        self.assertEqual(summary["cash_cents"], 80000)
        self.assertEqual(
            summary["holdings"]["AAPL"]["shares"], 1
        )

    def test_insufficient_funds(self):
        with self.assertRaises(ValueError):
            self.broker.buy_stock("AAPL", 10)


if __name__ == "__main__":
    unittest.main()

