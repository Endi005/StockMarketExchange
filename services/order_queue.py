import logging
import threading
from concurrent.futures import Future
from queue import Queue

from models.order import Order

from services.correlation_context import (
    correlation_scope,
    get_correlation_id,
    generate_correlation_id
)


logger = logging.getLogger("broker.orders")


class OrderQueue:
    """Single-worker, persistent order-processing queue."""

    def __init__(self, processor):

        self._processor = processor
        self._jobs = Queue()
        self._lock = threading.Lock()
        self._worker = None
        self._running = False
        self._stopping = False

    def start(self):

        with self._lock:

            if self._running or self._stopping:
                raise RuntimeError(
                    "Order queue already running or stopping."
                )

            # Restore unfinished orders and their
            # original correlation IDs.
            for order_id in self._processor.pending_order_ids():

                order_record = self._processor.get_order(
                    order_id
                )

                correlation_id = order_record[
                    "correlation_id"
                ]

                self._jobs.put(
                    (
                        "process",
                        order_id,
                        None,
                        correlation_id
                    )
                )

                logger.info(
                    "Pending order recovered: "
                    "correlation_id=%s order_id=%s",
                    correlation_id,
                    order_id
                )

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
        safe_order = Order.from_record(
            order.to_record()
        )

        # Capture the original broker request context.
        correlation_id = get_correlation_id()

        if correlation_id is not None:
            safe_order.correlation_id = correlation_id

        return self._request(
            "submit",
            safe_order,
            safe_order.correlation_id
        )

    def get_order(self, order_id):

        return self._request(
            "get_order",
            order_id
        )

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

        return self._request(
            "cancel",
            order_id
        )

    def _request(
        self,
        action,
        payload,
        correlation_id=None
    ):

        future = Future()

        if correlation_id is None:
            correlation_id = (
                get_correlation_id()
                or generate_correlation_id()
            )

        with self._lock:

            if not self._running:
                raise RuntimeError(
                    "Order queue is not running."
                )

            self._jobs.put(
                (
                    action,
                    payload,
                    future,
                    correlation_id
                )
            )

        return future.result()

    def _run(self):

        while True:

            action, payload, future, correlation_id = (
                self._jobs.get()
            )

            try:

                if action == "stop":
                    return

                # Restore the context inside the worker thread.
                with correlation_scope(correlation_id):

                    self._execute_job(
                        action,
                        payload,
                        future
                    )

            except Exception as error:

                logger.error(
                    "Order queue operation failed: "
                    "correlation_id=%s action=%s "
                    "error_type=%s",
                    correlation_id,
                    action,
                    type(error).__name__
                )

                if future is not None:
                    future.set_exception(error)

                # Failed processing leaves the order PENDING.
                # It can be recovered after a restart.

            finally:

                self._jobs.task_done()

    def _execute_job(self, action, payload, future):

        if action == "submit":

            result = self._processor.submit(payload)

            # Processing happens asynchronously, after
            # the PENDING order has been saved.
            self._jobs.put(
                (
                    "process",
                    result["order_id"],
                    None,
                    result["correlation_id"]
                )
            )

        elif action == "process":

            result = self._processor.process(
                payload
            )

        elif action == "get_order":

            result = self._processor.get_order(
                payload
            )

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

            result = self._processor.cancel(
                payload
            )

        else:

            raise ValueError(
                "Unknown queue operation."
            )

        if future is not None:
            future.set_result(result)

    def wait_until_idle(self):
        """Wait until all currently queued jobs finish."""

        self._jobs.join()

    def stop(self):

        with self._lock:

            if self._stopping:

                worker = self._worker
                shutdown_owner = False

            elif not self._running:

                return

            else:

                self._running = False
                self._stopping = True
                worker = self._worker
                shutdown_owner = True

        if not shutdown_owner:

            worker.join()
            return

        # Finish all accepted jobs, including processing jobs
        # generated by previously accepted submissions.
        self._jobs.join()

        # Stop the worker only after the queue has drained.
        self._jobs.put(
            ("stop", None, None, None)
        )

        worker.join()

        with self._lock:

            self._worker = None
            self._stopping = False