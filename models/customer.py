

import hashlib
import hmac
import secrets

from models.portfolio import Portfolio


class CustomerAccount:

    def __init__(self, username, password, portfolio=None):
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Username cannot be empty.")

        if not isinstance(password, str) or len(password) < 8:
            raise ValueError(
                "Password must have at least 8 characters."
            )

        self.username = username.strip()
        self._salt = secrets.token_bytes(16)
        self._password_hash = self._hash_password(password)

        self.portfolio = (
            portfolio if portfolio is not None else Portfolio()
        )

    def _hash_password(self, password):
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            self._salt,
            200000
        )

    def authenticate(self, password):
        if not isinstance(password, str):
            return False

        attempted_hash = self._hash_password(password)

        return hmac.compare_digest(
            self._password_hash,
            attempted_hash
        )

    def get_portfolio(self):
        return self.portfolio.get_summary()

    def to_record(self):
        return {
            "username": self.username,
            "salt": self._salt.hex(),
            "password_hash": self._password_hash.hex(),
            "portfolio": self.portfolio.get_summary()
        }

    @classmethod
    def from_record(cls, record):
        if not isinstance(record, dict) or set(record) != {
            "username", "salt", "password_hash", "portfolio"
        }:
            raise ValueError("Invalid customer record.")

        username = record["username"]

        if not isinstance(username, str) or not username.strip():
            raise ValueError("Invalid username.")

        try:
            salt = bytes.fromhex(record["salt"])
            password_hash = bytes.fromhex(record["password_hash"])
        except (ValueError, TypeError) as error:
            raise ValueError(
                "Invalid stored credentials."
            ) from error

        if len(salt) != 16 or len(password_hash) != 32:
            raise ValueError("Invalid stored credentials.")

        portfolio = Portfolio.from_snapshot(
            record["portfolio"]
        )

        customer = cls.__new__(cls)
        customer.username = username.strip()
        customer._salt = salt
        customer._password_hash = password_hash
        customer.portfolio = portfolio

        return customer
