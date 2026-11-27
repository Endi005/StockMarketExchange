import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from models.stock import Stock
from repositories.exchange_repository import ExchangeRepository
from services.exchange_service import ExchangeService
from services.price_observer import PriceObserver
from services.price_audit_observer import PriceAuditObserver


class TestPriceAuditObserver(unittest.TestCase):

    def setUp(self):

        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.repository = ExchangeRepository(
            Path(self.directory.name) / "exchange.json"
        )

        self.exchange = ExchangeService(
            [Stock("Apple", "AAPL", 20000)],
            repository=self.repository
        )

        self.observer = PriceAuditObserver()

        self.exchange.add_observer(self.observer)

    def test_observer_implements_interface(self):

        self.assertIsInstance(
            self.observer,
            PriceObserver
        )

    def test_committed_price_change_is_logged(self):

        with self.assertLogs(
            "exchange.market",
            level="INFO"
        ) as captured:

            self.exchange.update_price(
                "AAPL",
                20500
            )

        self.assertEqual(len(captured.output), 1)

        self.assertIn(
            "Market price committed",
            captured.output[0]
        )

        self.assertIn(
            "symbol=AAPL",
            captured.output[0]
        )

        self.assertIn(
            "price_cents=20500",
            captured.output[0]
        )

        self.assertEqual(
            self.exchange.get_price("AAPL"),
            20500
        )

    def test_automatic_market_tick_is_logged(self):

        with self.assertLogs(
            "exchange.market",
            level="INFO"
        ) as captured:

            prices = self.exchange.simulate_tick()

        self.assertEqual(
            prices["AAPL"],
            20200
        )

        self.assertIn(
            "symbol=AAPL price_cents=20200",
            captured.output[0]
        )

    def test_failed_persistence_does_not_publish_event(self):

        with patch.object(
            self.repository,
            "save",
            side_effect=OSError("Simulated disk failure")
        ):

            with self.assertNoLogs(
                "exchange.market",
                level="INFO"
            ):

                with self.assertRaises(OSError):

                    self.exchange.update_price(
                        "AAPL",
                        20500
                    )

        self.assertEqual(
            self.exchange.get_price("AAPL"),
            20000
        )

        self.assertEqual(
            self.exchange.get_history("AAPL"),
            [20000]
        )

    def test_removed_observer_receives_no_events(self):

        self.exchange.remove_observer(
            self.observer
        )

        with self.assertNoLogs(
            "exchange.market",
            level="INFO"
        ):

            self.exchange.update_price(
                "AAPL",
                20500
            )

        self.assertEqual(
            self.exchange.get_price("AAPL"),
            20500
        )

    def test_duplicate_registration_does_not_duplicate_logs(self):

        self.exchange.add_observer(
            self.observer
        )

        with self.assertLogs(
            "exchange.market",
            level="INFO"
        ) as captured:

            self.exchange.update_price(
                "AAPL",
                20500
            )

        self.assertEqual(
            len(captured.output),
            1
        )


if __name__ == "__main__":
    unittest.main()
