
import logging
import tempfile
import unittest
from pathlib import Path

from services.logging_setup import configure_logging


class TestLoggingSetup(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.log_path = Path(self.directory.name)

        self.original_handlers = {
            name: list(logging.getLogger(name).handlers)
            for name in ("broker", "exchange")
        }

        self.addCleanup(self.restore_loggers)

    def restore_loggers(self):
        for name in ("broker", "exchange"):
            logger = logging.getLogger(name)

            for handler in list(logger.handlers):
                if handler not in self.original_handlers[name]:
                    logger.removeHandler(handler)
                    handler.close()

    def test_broker_log_file(self):
        logger = configure_logging(
            "broker", self.log_path
        )

        logger.info("Broker started")

        content = (
            self.log_path / "broker.log"
        ).read_text(encoding="utf-8")

        self.assertIn("Broker started", content)
        self.assertIn("INFO", content)

    def test_exchange_log_file(self):
        logger = configure_logging(
            "exchange", self.log_path
        )

        logger.warning("Price update delayed")

        content = (
            self.log_path / "exchange.log"
        ).read_text(encoding="utf-8")

        self.assertIn("Price update delayed", content)
        self.assertIn("WARNING", content)

    def test_duplicate_configuration(self):
        first = configure_logging(
            "broker", self.log_path
        )

        original_count = len(first.handlers)

        second = configure_logging(
            "broker", self.log_path
        )

        self.assertIs(first, second)
        self.assertEqual(
            len(second.handlers),
            original_count
        )

    def test_unknown_server_rejected(self):
        with self.assertRaises(ValueError):
            configure_logging(
                "unknown", self.log_path
            )


if __name__ == "__main__":
    unittest.main()
