
import json
import os
import tempfile
from pathlib import Path

from models.customer import CustomerAccount


class CustomerRepository:

    def __init__(self, file_path):
        self._file_path = Path(file_path)

    def load(self):
        if not self._file_path.exists():
            return {}

        try:
            with self._file_path.open(
                "r", encoding="utf-8"
            ) as file:
                records = json.load(file)

        except (OSError, ValueError, UnicodeError) as error:
            raise ValueError(
                "Customer data cannot be read."
            ) from error

        if not isinstance(records, dict):
            raise ValueError("Invalid customer database.")

        customers = {}

        for username, record in records.items():
            customer = CustomerAccount.from_record(record)

            if username != customer.username:
                raise ValueError(
                    "Customer record has an invalid username."
                )

            customers[username] = customer

        return customers

    def save(self, customers):
        if not isinstance(customers, dict):
            raise ValueError("Invalid customer collection.")

        records = {}

        for username, customer in customers.items():
            if (
                not isinstance(customer, CustomerAccount)
                or username != customer.username
            ):
                raise ValueError("Invalid customer account.")

            records[username] = customer.to_record()

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
                json.dump(records, temporary_file)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            os.replace(temporary_path, self._file_path)

        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
