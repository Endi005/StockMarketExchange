
import json
import os
import tempfile
from pathlib import Path

from models.customer import CustomerAccount
from models.order import Order


class TradingRepository:
    """Atomically stores customers and their orders."""

    def __init__(self, file_path):
        self._file_path = Path(file_path)

    def load(self):
        if not self._file_path.exists():
            return {}, {}

        try:
            with self._file_path.open(
                "r", encoding="utf-8"
            ) as file:
                data = json.load(file)
        except (OSError, ValueError, UnicodeError) as error:
            raise ValueError(
                "Trading data cannot be read."
            ) from error

        if not isinstance(data, dict) or set(data) != {
            "customers", "orders"
        }:
            raise ValueError("Invalid trading database.")

        if (
            not isinstance(data["customers"], dict)
            or not isinstance(data["orders"], dict)
        ):
            raise ValueError("Invalid trading collections.")

        customers = {}

        for username, record in data["customers"].items():
            customer = CustomerAccount.from_record(record)

            if username != customer.username:
                raise ValueError("Invalid saved customer.")

            customers[username] = customer

        orders = {}

        for order_id, record in data["orders"].items():
            order = Order.from_record(record)

            if order_id != order.order_id:
                raise ValueError("Invalid saved order ID.")

            if order.username not in customers:
                raise ValueError(
                    "Order references an unknown customer."
                )

            orders[order_id] = order

        return customers, orders

    def save(self, customers, orders):
        if (
            not isinstance(customers, dict)
            or not isinstance(orders, dict)
        ):
            raise ValueError("Invalid trading collections.")

        customer_records = {}

        for username, customer in customers.items():
            if (
                not isinstance(customer, CustomerAccount)
                or username != customer.username
            ):
                raise ValueError("Invalid customer account.")

            record = customer.to_record()
            CustomerAccount.from_record(record)
            customer_records[username] = record

        order_records = {}

        for order_id, order in orders.items():
            if (
                not isinstance(order, Order)
                or order_id != order.order_id
                or order.username not in customers
            ):
                raise ValueError("Invalid trading order.")

            record = order.to_record()
            Order.from_record(record)
            order_records[order_id] = record

        data = {
            "customers": customer_records,
            "orders": order_records
        }

        self._file_path.parent.mkdir(
            parents=True, exist_ok=True
        )

        temporary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._file_path.parent,
                suffix=".tmp",
                delete=False
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)

                json.dump(data, temporary_file)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            os.replace(temporary_path, self._file_path)

        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
