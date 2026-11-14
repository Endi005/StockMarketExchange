
import json
import os
import tempfile
from pathlib import Path


class PortfolioRepository:

    def __init__(self, file_path):
        self._file_path = Path(file_path)

    def save(self, portfolio_data):
        self._validate(portfolio_data)
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
                json.dump(portfolio_data, temporary_file)
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
                "Stored portfolio is invalid or unreadable."
            ) from error

        self._validate(data)
        return data

    @staticmethod
    def _validate(data):
        if not isinstance(data, dict):
            raise ValueError("Portfolio must be an object.")

        if set(data) != {"cash_cents", "holdings"}:
            raise ValueError("Invalid portfolio fields.")

        cash = data["cash_cents"]
        holdings = data["holdings"]

        if type(cash) is not int or cash < 0:
            raise ValueError("Invalid portfolio cash.")

        if not isinstance(holdings, dict):
            raise ValueError("Invalid holdings format.")

        for symbol, position in holdings.items():
            if (
                not isinstance(symbol, str)
                or not symbol
                or symbol != symbol.strip().upper()
            ):
                raise ValueError("Invalid stock symbol.")

            if not isinstance(position, dict) or set(position) != {
                "shares", "total_paid_cents"
            }:
                raise ValueError("Invalid holding fields.")

            shares = position["shares"]
            paid = position["total_paid_cents"]

            if type(shares) is not int or shares <= 0:
                raise ValueError("Invalid share quantity.")

            if type(paid) is not int or paid < 0:
                raise ValueError("Invalid purchase cost.")
