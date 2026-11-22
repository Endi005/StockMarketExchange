
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


    def test_price_history_observer(self):
        from services.price_history_observer import PriceHistoryObserver

        history = {"AAPL": [20000]}
        observer = PriceHistoryObserver(history)

        observer.on_price_changed("AAPL", 22000)

        self.assertEqual(
            history["AAPL"],
            [20000, 22000]
        )

    def test_observer_receives_automatic_price_updates(self):
        class RecordingObserver:
            def __init__(self):
                self.events = []

            def on_price_changed(self, symbol, new_price):
                self.events.append((symbol, new_price))

        observer = RecordingObserver()
        self.exchange._observers.append(observer)

        self.exchange.simulate_tick()

        self.assertEqual(len(observer.events), 2)

        for symbol, price in observer.events:
            self.assertEqual(
                price,
                self.exchange.get_price(symbol)
            )

    def test_failed_observer_does_not_change_stock(self):
        class FailingObserver:
            def on_price_changed(self, symbol, new_price):
                raise RuntimeError("Observer failed")

        self.exchange._observers.append(FailingObserver())

        original_price = self.exchange.get_price("AAPL")
        original_history = self.exchange.get_history("AAPL")

        with self.assertRaises(RuntimeError):
            self.exchange.update_price("AAPL", 22000)

        self.assertEqual(
            self.exchange.get_price("AAPL"),
            original_price
        )

        self.assertEqual(
            self.exchange.get_history("AAPL"),
            original_history
        )



if __name__ == "__main__":
    unittest.main()

