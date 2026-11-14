
import unittest

from models.stock import Stock


class TestStock(unittest.TestCase):

    def test_create_stock(self):
        stock = Stock("Apple", "AAPL", 20000)
        self.assertEqual(stock.get_price(), 20000)

    def test_update_price(self):
        stock = Stock("Apple", "AAPL", 20000)
        stock.update_price(25000)
        self.assertEqual(stock.get_price(), 25000)

    def test_negative_price(self):
        stock = Stock("Apple", "AAPL", 20000)

        with self.assertRaises(ValueError):
            stock.update_price(-100)


if __name__ == "__main__":
    unittest.main()
