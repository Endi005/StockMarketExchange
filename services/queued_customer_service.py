
import secrets
import threading

from models.order import Order


class QueuedCustomerService:
    """Connects customer sessions to the order queue."""

    def __init__(self, order_queue):
        self._order_queue = order_queue
        self._sessions = {}
        self._lock = threading.Lock()

    def register(self, username, password):
        return self._order_queue.register_customer(
            username, password
        )

    def login(self, username, password):
        verified_username = (
            self._order_queue.authenticate_customer(
                username, password
            )
        )

        token = secrets.token_urlsafe(32)

        with self._lock:
            self._sessions[token] = verified_username

        return token

    def get_username(self, token):
        with self._lock:
            if (
                not isinstance(token, str)
                or token not in self._sessions
            ):
                raise ValueError(
                    "Access refused: invalid session. Log in again."
                )

            return self._sessions[token]

    def logout(self, token):
        with self._lock:
            if (
                not isinstance(token, str)
                or token not in self._sessions
            ):
                raise ValueError(
                    "Access refused: invalid session."
                )

            del self._sessions[token]

        return True

    def get_portfolio(self, token):
        username = self.get_username(token)

        return self._order_queue.get_customer_portfolio(
            username
        )

    def buy_stock(self, token, symbol, quantity):
        return self._trade(token, symbol, quantity, "buy")

    def sell_stock(self, token, symbol, quantity):
        return self._trade(token, symbol, quantity, "sell")

    def _trade(self, token, symbol, quantity, side):
        username = self.get_username(token)

        order = Order(
            username,
            symbol,
            side,
            quantity
        )

        return self._order_queue.submit(order)

    def get_order(self, token, order_id):
        username = self.get_username(token)
        order = self._order_queue.get_order(order_id)

        # Customers must never read another account's orders.
        if order["username"] != username:
            raise ValueError("Order not found.")

        return order

    def cancel_order(self, token, order_id):
        # Verify ownership before attempting cancellation.
        self.get_order(token, order_id)

        return self._order_queue.cancel(order_id)

    def get_statistics(self):
        return self._order_queue.get_statistics()
