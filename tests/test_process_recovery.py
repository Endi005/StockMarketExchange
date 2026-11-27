import subprocess
import sys
import tempfile
import unittest

from pathlib import Path
from unittest.mock import Mock

from models.customer import CustomerAccount
from models.order import Order
from repositories.trading_repository import TradingRepository
from services.order_processor import OrderProcessor
from services.order_queue import OrderQueue


CHILD_PROGRAM = """
import os
import sys
import time

from unittest.mock import Mock, patch

from models.order import Order
from repositories.trading_repository import TradingRepository
from services.order_processor import OrderProcessor
from services.order_queue import OrderQueue


database_path = sys.argv[1]
order_id = sys.argv[2]
scenario = sys.argv[3]

repository = TradingRepository(database_path)

gateway = Mock()
gateway.get_price.return_value = 20000

processor = OrderProcessor(repository, gateway)

order = Order(
    "Frank",
    "AAPL",
    "buy",
    2,
    order_id=order_id
)


def interrupt_process():
    print("READY_TO_TERMINATE", flush=True)

    while True:
        time.sleep(1)


if scenario == "pending":

    def interrupted_price(symbol):
        interrupt_process()

    gateway.get_price.side_effect = interrupted_price

    queue = OrderQueue(processor)
    queue.start()
    queue.submit(order)
    queue.wait_until_idle()


elif scenario == "during_save":

    processor.submit(order)

    def interrupted_replace(source, destination):
        interrupt_process()

    with patch(
        "repositories.trading_repository.os.replace",
        side_effect=interrupted_replace
    ):
        processor.process(order_id)


elif scenario == "filled":

    queue = OrderQueue(processor)
    queue.start()

    queue.submit(order)
    queue.wait_until_idle()

    result = queue.get_order(order_id)

    if result["status"] != "FILLED":
        raise RuntimeError("Order was not filled.")

    interrupt_process()


else:
    raise ValueError("Unknown recovery scenario.")
"""


class TestProcessRecovery(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.database_path = (
            Path(self.directory.name) / "trading.json"
        )

        self.repository = TradingRepository(
            self.database_path
        )

        customer = CustomerAccount(
            "Frank",
            "password123"
        )

        self.repository.save(
            {"Frank": customer},
            {}
        )

        self.order = Order(
            "Frank",
            "AAPL",
            "buy",
            2
        )

        self.gateway = Mock()
        self.gateway.get_price.return_value = 20000

    def terminate_child(self, scenario):

        import threading
        from queue import Queue, Empty

        project_root = (
            Path(__file__).resolve().parents[1]
        )

        process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-c",
                CHILD_PROGRAM,
                str(self.database_path),
                self.order.order_id,
                scenario
            ],
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8"
        )

        messages = Queue()

        def read_output():
            for line in process.stdout:
                messages.put(line.strip())

            messages.put(None)

        reader = threading.Thread(
            target=read_output,
            daemon=True
        )

        reader.start()

        output = []

        try:
            import time

            deadline = time.monotonic() + 15

            while True:

                remaining = deadline - time.monotonic()

                if remaining <= 0:
                    self.fail(
                        "Child process did not reach "
                        "the interruption point."
                    )

                try:
                    line = messages.get(
                        timeout=remaining
                    )

                except Empty:
                    self.fail(
                        "Timed out waiting for child process."
                    )

                if line is None:
                    self.fail(
                        "Child exited unexpectedly: "
                        + "\\n".join(output)
                    )

                output.append(line)

                if line == "READY_TO_TERMINATE":
                    break

            self.assertIsNone(process.poll())

            # Force termination without graceful shutdown.
            process.kill()
            process.wait(timeout=10)

            self.assertNotEqual(
                process.returncode,
                0
            )

        finally:

            if process.poll() is None:
                process.kill()

            process.wait(timeout=10)
            reader.join(timeout=5)
            process.stdout.close()

    def restart_queue(self):

        repository = TradingRepository(
            self.database_path
        )

        processor = OrderProcessor(
            repository,
            self.gateway
        )

        queue = OrderQueue(processor)

        self.addCleanup(queue.stop)

        queue.start()
        queue.wait_until_idle()

        return queue

    def assert_pending_database(self):

        customers, orders = self.repository.load()

        saved_order = orders[self.order.order_id]

        self.assertEqual(
            saved_order.status,
            "PENDING"
        )

        self.assertEqual(
            saved_order.correlation_id,
            self.order.correlation_id
        )

        portfolio = customers["Frank"].get_portfolio()

        self.assertEqual(
            portfolio["cash_cents"],
            100000
        )

        self.assertEqual(
            portfolio["holdings"],
            {}
        )

    def assert_filled_database(self):

        customers, orders = self.repository.load()

        self.assertEqual(len(orders), 1)

        saved_order = orders[self.order.order_id]

        self.assertEqual(
            saved_order.status,
            "FILLED"
        )

        self.assertEqual(
            saved_order.correlation_id,
            self.order.correlation_id
        )

        portfolio = customers["Frank"].get_portfolio()

        self.assertEqual(
            portfolio["cash_cents"],
            60000
        )

        self.assertEqual(
            portfolio["holdings"]["AAPL"]["shares"],
            2
        )

    def test_process_crash_preserves_pending_order(self):

        self.terminate_child("pending")

        self.assert_pending_database()

        queue = self.restart_queue()

        result = queue.get_order(
            self.order.order_id
        )

        self.assertEqual(
            result["status"],
            "FILLED"
        )

        self.assert_filled_database()

        self.gateway.get_price.assert_called_once_with(
            "AAPL"
        )

    def test_process_crash_during_atomic_save(self):

        self.terminate_child("during_save")

        # The previous database must remain readable.
        self.assert_pending_database()

        # Forced termination can leave an orphaned
        # temporary file, but not a partially replaced
        # trading database.
        temporary_files = list(
            self.database_path.parent.glob("*.tmp")
        )

        self.assertTrue(temporary_files)

        queue = self.restart_queue()

        result = queue.get_order(
            self.order.order_id
        )

        self.assertEqual(
            result["status"],
            "FILLED"
        )

        self.assert_filled_database()

        self.gateway.get_price.assert_called_once_with(
            "AAPL"
        )

    def test_process_crash_after_fill_does_not_duplicate(self):

        self.terminate_child("filled")

        self.assert_filled_database()

        queue = self.restart_queue()

        result = queue.get_order(
            self.order.order_id
        )

        self.assertEqual(
            result["status"],
            "FILLED"
        )

        self.assert_filled_database()

        # Recovery must not request another price
        # for an already completed order.
        self.gateway.get_price.assert_not_called()


if __name__ == "__main__":
    unittest.main()