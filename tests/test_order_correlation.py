import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from models.order import Order
from repositories.trading_repository import TradingRepository
from services.order_processor import OrderProcessor
from services.order_queue import OrderQueue

from services.correlation_context import (
    correlation_scope,
    get_correlation_id
)


class TestOrderCorrelation(unittest.TestCase):

    def setUp(self):

        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

        self.path = (
            Path(self.folder.name) / "trading.json"
        )

        self.repository = TradingRepository(self.path)

        self.gateway = Mock()
        self.observed_ids = []

        def get_price(symbol):

            self.observed_ids.append(
                get_correlation_id()
            )

            return 100

        self.gateway.get_price.side_effect = get_price

        self.processor = OrderProcessor(
            self.repository,
            self.gateway
        )

        self.processor.register_customer(
            "Frank",
            "SecurePass123!"
        )

        self.correlation_id = "a" * 32

    def start_queue(self, processor):

        queue = OrderQueue(processor)
        queue.start()

        self.addCleanup(queue.stop)

        return queue

    def test_order_preserves_correlation_id(self):

        order = Order(
            "Frank",
            "AAPL",
            "buy",
            1,
            correlation_id=self.correlation_id
        )

        restored = Order.from_record(
            order.to_record()
        )

        self.assertEqual(
            restored.correlation_id,
            self.correlation_id
        )

    def test_legacy_order_uses_order_id(self):

        order = Order(
            "Frank", "AAPL", "buy", 1
        )

        record = order.to_record()

        del record["correlation_id"]

        restored = Order.from_record(record)

        self.assertEqual(
            restored.correlation_id,
            restored.order_id
        )

    def test_invalid_saved_correlation_rejected(self):

        order = Order(
            "Frank", "AAPL", "buy", 1
        )

        for invalid_id in (
            None,
            "",
            "invalid",
            "g" * 32,
            "a" * 31,
            123
        ):

            with self.subTest(value=invalid_id):

                record = order.to_record()

                record["correlation_id"] = invalid_id

                with self.assertRaises(ValueError):

                    Order.from_record(record)

    def test_queue_propagates_request_context(self):

        queue = self.start_queue(self.processor)

        order = Order(
            "Frank", "AAPL", "buy", 1
        )

        original_id = order.correlation_id

        with correlation_scope(self.correlation_id):

            accepted = queue.submit(order)

        queue.wait_until_idle()

        self.assertEqual(
            accepted["correlation_id"],
            self.correlation_id
        )

        self.assertEqual(
            self.observed_ids,
            [self.correlation_id]
        )

        self.assertEqual(
            order.correlation_id,
            original_id
        )

        completed = queue.get_order(
            accepted["order_id"]
        )

        self.assertEqual(
            completed["status"],
            "FILLED"
        )

        self.assertEqual(
            completed["correlation_id"],
            self.correlation_id
        )

        self.assertIsNone(get_correlation_id())

    def test_different_orders_keep_separate_contexts(self):

        queue = self.start_queue(self.processor)

        first_id = "a" * 32
        second_id = "b" * 32

        with correlation_scope(first_id):

            first = queue.submit(
                Order("Frank", "AAPL", "buy", 1)
            )

        with correlation_scope(second_id):

            second = queue.submit(
                Order("Frank", "AAPL", "buy", 1)
            )

        queue.wait_until_idle()

        self.assertEqual(
            self.observed_ids,
            [first_id, second_id]
        )

        self.assertEqual(
            first["correlation_id"],
            first_id
        )

        self.assertEqual(
            second["correlation_id"],
            second_id
        )

    def test_recovery_preserves_original_correlation(self):

        order = Order(
            "Frank",
            "AAPL",
            "buy",
            1,
            correlation_id=self.correlation_id
        )

        self.processor.submit(order)

        # Reconstruct the processor from persistent storage.
        recovered_repository = TradingRepository(
            self.path
        )

        recovered_processor = OrderProcessor(
            recovered_repository,
            self.gateway
        )

        queue = self.start_queue(
            recovered_processor
        )

        queue.wait_until_idle()

        completed = queue.get_order(
            order.order_id
        )

        self.assertEqual(
            completed["status"],
            "FILLED"
        )

        self.assertEqual(
            completed["correlation_id"],
            self.correlation_id
        )

        self.assertEqual(
            self.observed_ids,
            [self.correlation_id]
        )

    def test_context_restored_after_execution_failure(self):

        order = Order(
            "Frank",
            "AAPL",
            "buy",
            1,
            correlation_id=self.correlation_id
        )

        self.processor.submit(order)

        self.gateway.get_price.side_effect = (
            RuntimeError("Exchange unavailable")
        )

        outer_id = "b" * 32

        with correlation_scope(outer_id):

            with self.assertRaises(RuntimeError):

                self.processor.process(
                    order.order_id
                )

            self.assertEqual(
                get_correlation_id(),
                outer_id
            )

        saved_order = self.processor.get_order(
            order.order_id
        )

        self.assertEqual(
            saved_order["status"],
            "PENDING"
        )

        self.assertEqual(
            saved_order["correlation_id"],
            self.correlation_id
        )

        self.assertIsNone(get_correlation_id())

    def test_trade_audit_contains_correlation_id(self):

        order = Order(
            "Frank",
            "AAPL",
            "buy",
            1,
            correlation_id=self.correlation_id
        )

        with self.assertLogs(
            "broker.orders",
            level="INFO"
        ) as captured:

            self.processor.submit(order)

            self.processor.process(
                order.order_id
            )

        logs = "\n".join(captured.output)

        self.assertIn(
            "Order accepted",
            logs
        )

        self.assertIn(
            "Order execution started",
            logs
        )

        self.assertIn(
            "Order execution completed",
            logs
        )

        self.assertIn(
            self.correlation_id,
            logs
        )

        self.assertIn(
            order.order_id,
            logs
        )

        self.assertIn(
            "status=FILLED",
            logs
        )


if __name__ == "__main__":
    unittest.main()