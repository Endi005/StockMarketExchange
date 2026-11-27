
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

from models.customer import CustomerAccount
from models.order import Order
from repositories.trading_repository import TradingRepository
from services.order_processor import OrderProcessor
from services.order_queue import OrderQueue


class TestOrderConcurrency(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.repository = TradingRepository(
            Path(self.directory.name) / "trading.json"
        )

        frank = CustomerAccount("Frank", "password123")
        emma = CustomerAccount("Emma", "password456")

        self.repository.save(
            {"Frank": frank, "Emma": emma},
            {}
        )

        self.gateway = Mock()
        self.gateway.get_price.return_value = 20000

        self.processor = OrderProcessor(
            self.repository,
            self.gateway
        )

        self.queue = OrderQueue(self.processor)
        self.addCleanup(self.queue.stop)
        self.queue.start()

    def submit_concurrently(self, orders):
        barrier = threading.Barrier(len(orders))

        def submit_order(order):
            barrier.wait(timeout=10)
            return self.queue.submit(order)

        with ThreadPoolExecutor(
            max_workers=len(orders)
        ) as executor:
            results = list(
                executor.map(submit_order, orders)
            )

        self.queue.wait_until_idle()

        return results

    def test_concurrent_orders_cannot_overspend(self):
        orders = [
            Order("Frank", "AAPL", "buy", 1)
            for _ in range(10)
        ]

        self.submit_concurrently(orders)

        results = [
            self.queue.get_order(order.order_id)
            for order in orders
        ]

        statuses = [
            result["status"] for result in results
        ]

        self.assertEqual(statuses.count("FILLED"), 5)
        self.assertEqual(statuses.count("REJECTED"), 5)

        portfolio = self.queue.get_customer_portfolio(
            "Frank"
        )

        self.assertEqual(portfolio["cash_cents"], 0)

        self.assertEqual(
            portfolio["holdings"]["AAPL"]["shares"],
            5
        )

    def test_multiple_customers_trade_concurrently(self):
        orders = [
            Order("Frank", "AAPL", "buy", 1)
            for _ in range(3)
        ]

        orders += [
            Order("Emma", "AAPL", "buy", 1)
            for _ in range(4)
        ]

        self.submit_concurrently(orders)

        for order in orders:
            result = self.queue.get_order(
                order.order_id
            )
            self.assertEqual(result["status"], "FILLED")

        frank = self.queue.get_customer_portfolio(
            "Frank"
        )

        emma = self.queue.get_customer_portfolio(
            "Emma"
        )

        self.assertEqual(frank["cash_cents"], 40000)
        self.assertEqual(emma["cash_cents"], 20000)

        self.assertEqual(
            frank["holdings"]["AAPL"]["shares"], 3
        )

        self.assertEqual(
            emma["holdings"]["AAPL"]["shares"], 4
        )

    def test_high_volume_orders_are_not_lost(self):
        self.gateway.get_price.return_value = 100

        orders = [
            Order("Frank", "AAPL", "buy", 1)
            for _ in range(100)
        ]

        with ThreadPoolExecutor(
            max_workers=10
        ) as executor:
            results = list(
                executor.map(self.queue.submit, orders)
            )

        self.queue.wait_until_idle()

        self.assertEqual(len(results), 100)

        customers, saved_orders = self.repository.load()

        self.assertEqual(len(saved_orders), 100)

        self.assertEqual(
            set(saved_orders),
            {order.order_id for order in orders}
        )

        for order in orders:
            result = self.queue.get_order(
                order.order_id
            )
            self.assertEqual(result["status"], "FILLED")

        portfolio = customers["Frank"].get_portfolio()

        self.assertEqual(
            portfolio["cash_cents"], 90000
        )

        self.assertEqual(
            portfolio["holdings"]["AAPL"]["shares"],
            100
        )

    def test_completed_order_cannot_execute_twice(self):
        order = Order("Frank", "AAPL", "buy", 2)

        self.queue.submit(order)
        self.queue.wait_until_idle()
        self.queue.stop()

        # Recreate the processor from persistent storage.
        restarted_repository = TradingRepository(
            Path(self.directory.name) / "trading.json"
        )

        restarted_processor = OrderProcessor(
            restarted_repository,
            self.gateway
        )

        # Explicitly attempt to process the completed order.
        result = restarted_processor.process(
            order.order_id
        )

        self.assertEqual(result["status"], "FILLED")

        portfolio = (
            restarted_processor.get_customer_portfolio(
                "Frank"
            )
        )

        self.assertEqual(
            portfolio["cash_cents"], 60000
        )

        self.assertEqual(
            portfolio["holdings"]["AAPL"]["shares"],
            2
        )

        self.gateway.get_price.assert_called_once()

      
    def test_shutdown_drains_accepted_orders(self):
        entered = threading.Event()
        release = threading.Event()

        original_submit = self.processor.submit

        def delayed_submit(order):
            entered.set()

            if not release.wait(timeout=10):
                raise TimeoutError("Test timed out.")

            return original_submit(order)

        self.processor.submit = delayed_submit

        order = Order("Frank", "AAPL", "buy", 2)

        with ThreadPoolExecutor(max_workers=2) as executor:
            submission = executor.submit(
                self.queue.submit, order
            )

            try:
                self.assertTrue(entered.wait(timeout=5))

                shutdown = executor.submit(self.queue.stop)

                # Wait until shutdown stops accepting requests.
                import time

                deadline = time.monotonic() + 5

                while time.monotonic() < deadline:
                    with self.queue._lock:
                        if not self.queue._running:
                            break

                    time.sleep(0.01)

                with self.queue._lock:
                    self.assertFalse(self.queue._running)

                self.assertFalse(shutdown.done())

            finally:
                release.set()

            submission.result(timeout=10)
            shutdown.result(timeout=10)

        customers, orders = self.repository.load()

        self.assertEqual(
            orders[order.order_id].status,
            "FILLED"
        )

        portfolio = customers["Frank"].get_portfolio()

        self.assertEqual(portfolio["cash_cents"], 60000)

        self.assertEqual(
            portfolio["holdings"]["AAPL"]["shares"],
            2
        )
  


if __name__ == "__main__":
    unittest.main()
