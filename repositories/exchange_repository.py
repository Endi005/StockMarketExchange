
import json
import os
import tempfile
from pathlib import Path


class ExchangeRepository:

    def __init__(self, file_path):
        self._file_path = Path(file_path)

    def save(self, data):
        self._validate(data)

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

    def load(self):
        if not self._file_path.exists():
            return None

        try:
            with self._file_path.open(
                "r", encoding="utf-8"
            ) as file:
                data = json.load(file)

        except (OSError, ValueError, UnicodeError) as error:
            raise ValueError(
                "Exchange data is unreadable. Restore a valid file."
            ) from error

        self._validate(data)
        return data

    @staticmethod
    def _validate(data):
        if not isinstance(data, dict) or set(data) != {"stocks"}:
            raise ValueError("Invalid exchange data format.")

        stocks = data["stocks"]

        if not isinstance(stocks, dict) or not stocks:
            raise ValueError("Exchange must contain stocks.")

        for symbol, stock in stocks.items():
            if (
                not isinstance(symbol, str)
                or not symbol
                or symbol != symbol.strip().upper()
            ):
                raise ValueError("Invalid stock symbol.")

            if not isinstance(stock, dict) or set(stock) != {
                "name", "price_cents", "history"
            }:
                raise ValueError("Invalid stock record.")

            name = stock["name"]
            price = stock["price_cents"]
            history = stock["history"]

            if not isinstance(name, str) or not name.strip():
                raise ValueError("Invalid stock name.")

            if type(price) is not int or price <= 0:
                raise ValueError("Invalid stock price.")

            if (
                not isinstance(history, list)
                or not history
                or any(
                    type(value) is not int or value <= 0
                    for value in history
                )
                or history[-1] != price
            ):
                raise ValueError("Invalid stock price history.")
