
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from models.stock import Stock
from services.exchange_service import ExchangeService
from repositories.exchange_repository import ExchangeRepository


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


if __name__ == "__main__":
    unittest.main()
