import unittest

from models.stock import Stock
from services.exchange_service import ExchangeService
from services.price_observer import PriceObserver
from services.price_history_observer import PriceHistoryObserver


class RecordingObserver(PriceObserver):

    def __init__(self):
        self.events = []

    def on_price_changed(self, symbol, new_price):
        self.events.append((symbol, new_price))


class FailingObserver(PriceObserver):

    def on_price_changed(self, symbol, new_price):
        raise RuntimeError("Observer failed")


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
        history = {"AAPL": [20000]}
        observer = PriceHistoryObserver(history)

        observer.on_price_changed("AAPL", 22000)

        self.assertEqual(
            history["AAPL"],
            [20000, 22000]
        )

    def test_observer_receives_automatic_price_updates(self):
        observer = RecordingObserver()

        self.exchange.add_observer(observer)
        self.exchange.simulate_tick()

        self.assertEqual(len(observer.events), 2)

        for symbol, price in observer.events:
            self.assertEqual(
                price,
                self.exchange.get_price(symbol)
            )

    def test_failed_observer_preserves_committed_update(self):
        self.exchange.add_observer(FailingObserver())

        with self.assertLogs(
            "exchange.market", level="ERROR"
        ) as logs:
            self.exchange.update_price("AAPL", 22000)

        self.assertEqual(
            self.exchange.get_price("AAPL"),
            22000
        )

        self.assertEqual(
            self.exchange.get_history("AAPL"),
            [20000, 22000]
        )

        self.assertIn(
            "Price observer failed",
            logs.output[0]
        )

    def test_observer_can_be_removed(self):
        observer = RecordingObserver()

        self.exchange.add_observer(observer)
        self.exchange.remove_observer(observer)

        self.exchange.update_price("AAPL", 22000)

        self.assertEqual(observer.events, [])

    def test_duplicate_observer_registration(self):
        observer = RecordingObserver()

        self.exchange.add_observer(observer)
        self.exchange.add_observer(observer)

        self.exchange.update_price("AAPL", 22000)

        self.assertEqual(
            observer.events,
            [("AAPL", 22000)]
        )

    def test_invalid_observer_is_rejected(self):
        with self.assertRaises(ValueError):
            self.exchange.add_observer(object())

    def test_multiple_observers_receive_updates(self):
        first = RecordingObserver()
        second = RecordingObserver()

        self.exchange.add_observer(first)
        self.exchange.add_observer(second)

        self.exchange.update_price("AAPL", 22000)

        self.assertEqual(
            first.events,
            [("AAPL", 22000)]
        )

        self.assertEqual(
            second.events,
            [("AAPL", 22000)]
        )

    def test_failed_observer_does_not_block_others(self):
        observer = RecordingObserver()

        self.exchange.add_observer(FailingObserver())
        self.exchange.add_observer(observer)

        with self.assertLogs(
            "exchange.market", level="ERROR"
        ):
            self.exchange.update_price("AAPL", 22000)

        self.assertEqual(
            observer.events,
            [("AAPL", 22000)]
        )

    def test_observer_receives_committed_price(self):
        exchange = self.exchange
        observed_prices = []

        class CheckingObserver(PriceObserver):

            def on_price_changed(self, symbol, new_price):
                observed_prices.append(
                    (new_price, exchange.get_price(symbol))
                )

        self.exchange.add_observer(CheckingObserver())
        self.exchange.update_price("AAPL", 22000)

        self.assertEqual(
            observed_prices,
            [(22000, 22000)]
        )


if __name__ == "__main__":
    unittest.main()