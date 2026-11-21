
import secrets

from models.order_state import (
    PendingState,
    state_from_name
)


class Order:
    """A stock order with a persistent lifecycle."""

    def __init__(
        self, username, symbol, side, quantity, order_id=None
    ):
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Order requires a valid customer.")

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Order requires a valid stock symbol.")

        if side not in ("buy", "sell"):
            raise ValueError("Order side must be buy or sell.")

        if type(quantity) is not int or quantity <= 0:
            raise ValueError("Order quantity must be positive.")

        if order_id is None:
            order_id = secrets.token_hex(16)

        if (
            not isinstance(order_id, str)
            or len(order_id) != 32
            or any(char not in "0123456789abcdef" for char in order_id)
        ):
            raise ValueError("Invalid order ID.")

        self.order_id = order_id
        self.username = username.strip()
        self.symbol = symbol.strip().upper()
        self.side = side
        self.quantity = quantity

        self._state = PendingState()
        self._history = ["PENDING"]
        self._price_cents = None
        self._result = None
        self._error = None

    @property
    def status(self):
        return self._state.name

    @property
    def is_terminal(self):
        return self._state.is_terminal

    def ensure_executable(self):
        return self._state.ensure_executable()

    def _expected_result(self, price_cents):
        amount = self.quantity * price_cents

        if self.side == "buy":
            return {
                "symbol": self.symbol,
                "shares": self.quantity,
                "cost_cents": amount
            }

        return {
            "symbol": self.symbol,
            "shares": self.quantity,
            "proceeds_cents": amount
        }

    def fill(self, price_cents, result):
        if type(price_cents) is not int or price_cents <= 0:
            raise ValueError("Invalid execution price.")

        if result != self._expected_result(price_cents):
            raise ValueError("Invalid execution result.")

        new_state = self._state.fill()

        self._state = new_state
        self._price_cents = price_cents
        self._result = result.copy()
        self._history.append(new_state.name)

    def reject(self, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Rejection requires a reason.")

        new_state = self._state.reject()

        self._state = new_state
        self._error = reason.strip()
        self._history.append(new_state.name)

    def cancel(self, reason="Cancelled by customer."):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Cancellation requires a reason.")

        new_state = self._state.cancel()

        self._state = new_state
        self._error = reason.strip()
        self._history.append(new_state.name)

    def to_record(self):
        return {
            "order_id": self.order_id,
            "username": self.username,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "status": self.status,
            "history": list(self._history),
            "price_cents": self._price_cents,
            "result": (
                self._result.copy()
                if self._result is not None
                else None
            ),
            "error": self._error
        }

    @classmethod
    def from_record(cls, record):
        required = {
            "order_id", "username", "symbol", "side",
            "quantity", "status", "history",
            "price_cents", "result", "error"
        }

        if not isinstance(record, dict) or set(record) != required:
            raise ValueError("Invalid saved order.")

        order = cls(
            record["username"],
            record["symbol"],
            record["side"],
            record["quantity"],
            record["order_id"]
        )

        if record["username"] != order.username:
            raise ValueError("Invalid saved customer.")

        if record["symbol"] != order.symbol:
            raise ValueError("Invalid saved stock symbol.")

        state = state_from_name(record["status"])

        expected_history = ["PENDING"]
        if state.name != "PENDING":
            expected_history.append(state.name)

        if record["history"] != expected_history:
            raise ValueError("Invalid order history.")

        price = record["price_cents"]
        result = record["result"]
        error = record["error"]

        if state.name == "PENDING":
            if price is not None or result is not None or error is not None:
                raise ValueError("Invalid pending order.")

        elif state.name == "FILLED":
            if (
                type(price) is not int
                or price <= 0
                or result != order._expected_result(price)
                or error is not None
            ):
                raise ValueError("Invalid filled order.")

        else:
            if (
                price is not None
                or result is not None
                or not isinstance(error, str)
                or not error.strip()
                or error != error.strip()
            ):
                raise ValueError("Invalid terminal order.")

        order._state = state
        order._history = list(expected_history)
        order._price_cents = price
        order._result = result.copy() if result is not None else None
        order._error = error

        return order
