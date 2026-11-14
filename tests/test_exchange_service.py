
import unittest

from models.stock import Stock
from services.exchange_service import ExchangeService


class TestExchangeService(unittest.TestCase):

    def setUp(self):
        self.exchange = ExchangeService([
            Stock("Apple", "AAPL", 20000),
            Stock("Tesla", "TSLA", 25000)
        ])

    def test_get_prices(self):
        prices = self.exchange.get_prices()

        self.assertEqual(prices["AAPL"], 20000)
        self.assertEqual(prices["TSLA"], 25000)

    def test_update_price(self):
        self.exchange.update_price("AAPL", 22000)

        self.assertEqual(
            self.exchange.get_price("AAPL"), 22000
        )

    def test_price_history(self):
        self.exchange.update_price("AAPL", 22000)

        self.assertEqual(
            self.exchange.get_history("AAPL"),
            [20000, 22000]
        )

    def test_invalid_stock(self):
        with self.assertRaises(ValueError):
            self.exchange.get_price("UNKNOWN")


if __name__ == "__main__":
    unittest.main()

