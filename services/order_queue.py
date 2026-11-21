
import logging
import threading
from concurrent.futures import Future
from queue import Queue

from models.order import Order


logger = logging.getLogger("broker.orders")


class OrderQueue:
    """Single-worker, persistent order-processing queue."""

    def __init__(self, processor):
        self._processor = processor
        self._jobs = Queue()
        self._lock = threading.Lock()
        self._worker = None
        self._running = False

    def start(self):
        with self._lock:
            if self._running:
                raise RuntimeError("Order queue already running.")

            # Restore unfinished orders from persistent storage.
            for order_id in self._processor.pending_order_ids():
                self._jobs.put(("process", order_id, None))

            self._worker = threading.Thread(
                target=self._run,
                name="OrderWorker",
                daemon=False
            )

            self._running = True
            self._worker.start()

        return self

    def submit(self, order):
        if not isinstance(order, Order):
            raise ValueError("Invalid order.")

        # Copy the order before handing it to another thread.
        safe_order = Order.from_record(order.to_record())

        return self._request("submit", safe_order)

    def get_order(self, order_id):
        return self._request("get_order", order_id)

    def register_customer(self, username, password):
        return self._request(
            "register_customer",
            (username, password)
        )

    def authenticate_customer(self, username, password):
        return self._request(
            "authenticate_customer",
            (username, password)
        )

    def get_customer_portfolio(self, username):
        return self._request(
            "get_customer_portfolio",
            username
        )

    def get_statistics(self):
        return self._request(
            "get_statistics",
            None
        )


    def cancel(self, order_id):
        return self._request("cancel", order_id)

    def _request(self, action, payload):
        future = Future()

        with self._lock:
            if not self._running:
                raise RuntimeError("Order queue is not running.")

            self._jobs.put((action, payload, future))

        return future.result()

    def _run(self):
        while True:
            action, payload, future = self._jobs.get()

            try:
                if action == "stop":
                    return

                if action == "submit":
                    result = self._processor.submit(payload)

                    # Processing happens asynchronously, after
                    # the PENDING order has been saved.
                    self._jobs.put(
                        ("process", result["order_id"], None)
                    )

                elif action == "process":
                    result = self._processor.process(payload)

                elif action == "get_order":
                    result = self._processor.get_order(payload)

                elif action == "register_customer":
                    username, password = payload

                    result = self._processor.register_customer(
                        username,
                        password
                    )

                elif action == "authenticate_customer":
                    username, password = payload

                    result = self._processor.authenticate_customer(
                        username,
                        password
                    )

                elif action == "get_customer_portfolio":
                    result = self._processor.get_customer_portfolio(
                        payload
                    )

                elif action == "get_statistics":
                    result = self._processor.get_statistics()


                elif action == "cancel":
                    result = self._processor.cancel(payload)

                else:
                    raise ValueError("Unknown queue operation.")

                if future is not None:
                    future.set_result(result)

            except Exception as error:
                logger.exception(
                    "Order queue operation failed: %s",
                    action
                )

                if future is not None:
                    future.set_exception(error)

                # Failed processing leaves the order PENDING.
                # It can be recovered after a restart.

            finally:
                self._jobs.task_done()

    def wait_until_idle(self):
        """Wait until all currently queued jobs finish."""
        self._jobs.join()

    def stop(self):
        with self._lock:
            if not self._running:
                return

            self._running = False
            self._jobs.put(("stop", None, None))
            worker = self._worker

        worker.join()
