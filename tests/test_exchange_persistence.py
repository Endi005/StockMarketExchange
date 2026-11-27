import tempfile
import threading
import unittest

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from models.stock import Stock
from services.exchange_service import ExchangeService
from repositories.exchange_repository import ExchangeRepository


class RecordingObserver:

    def __init__(self):
        self.events = []

    def on_price_changed(self, symbol, new_price):
        self.events.append((symbol, new_price))


class TestExchangePersistence(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.repository = ExchangeRepository(
            Path(self.directory.name) / "exchange.json"
        )

        self.exchange = ExchangeService(
            [
                Stock("Apple", "AAPL", 20000),
                Stock("Tesla", "TSLA", 25000)
            ],
            repository=self.repository
        )

    def test_prices_survive_restart(self):
        self.exchange.update_price("AAPL", 22000)

        restarted = ExchangeService(
            [],
            repository=self.repository
        )

        self.assertEqual(
            restarted.get_price("AAPL"), 22000
        )

        self.assertEqual(
            restarted.get_history("AAPL"),
            [20000, 22000]
        )

    def test_simulated_price_change(self):
        self.exchange.simulate_tick()

        self.assertEqual(
            self.exchange.get_price("AAPL"),
            20200
        )

        self.assertEqual(
            self.exchange.get_history("AAPL"),
            [20000, 20200]
        )

    def test_failed_save_preserves_original_price(self):
        with patch.object(
            self.repository,
            "save",
            side_effect=OSError("Disk unavailable")
        ):
            with self.assertRaises(OSError):
                self.exchange.update_price("AAPL", 22000)

        self.assertEqual(
            self.exchange.get_price("AAPL"),
            20000
        )

        self.assertEqual(
            self.exchange.get_history("AAPL"),
            [20000]
        )

    def test_failed_save_does_not_notify_observers(self):
        observer = RecordingObserver()
        self.exchange.add_observer(observer)

        with patch.object(
            self.repository,
            "save",
            side_effect=OSError("Disk unavailable")
        ):
            with self.assertRaises(OSError):
                self.exchange.update_price("AAPL", 22000)

        self.assertEqual(observer.events, [])

        restarted = ExchangeService(
            [],
            repository=self.repository
        )

        self.assertEqual(
            restarted.get_price("AAPL"),
            20000
        )

        self.assertEqual(
            restarted.get_history("AAPL"),
            [20000]
        )

    def test_concurrent_updates_are_not_lost(self):
        prices = list(range(21000, 21020))

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(
                    self.exchange.update_price,
                    "AAPL",
                    price
                )
                for price in prices
            ]

            for future in futures:
                future.result(timeout=10)

        history = self.exchange.get_history("AAPL")

        self.assertEqual(len(history), 21)
        self.assertEqual(history[0], 20000)
        self.assertCountEqual(history[1:], prices)

        restarted = ExchangeService(
            [],
            repository=self.repository
        )

        self.assertEqual(
            restarted.get_history("AAPL"),
            history
        )

        self.assertEqual(
            restarted.get_price("AAPL"),
            history[-1]
        )

    def test_readers_continue_during_disk_write(self):
        save_started = threading.Event()
        allow_save = threading.Event()

        original_save = self.repository.save

        def delayed_save(data):
            save_started.set()

            if not allow_save.wait(timeout=10):
                raise TimeoutError("Save was not released.")

            original_save(data)

        with patch.object(
            self.repository,
            "save",
            side_effect=delayed_save
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                update = executor.submit(
                    self.exchange.update_price,
                    "AAPL",
                    22000
                )

                try:
                    self.assertTrue(
                        save_started.wait(timeout=5)
                    )

                    reader = executor.submit(
                        self.exchange.get_price,
                        "AAPL"
                    )

                    self.assertEqual(
                        reader.result(timeout=5),
                        20000
                    )

                    self.assertFalse(update.done())

                finally:
                    allow_save.set()

                update.result(timeout=10)

        self.assertEqual(
            self.exchange.get_price("AAPL"),
            22000
        )


if __name__ == "__main__":
    unittest.main()