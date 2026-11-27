import logging

from models.customer import CustomerAccount
from models.order import Order
from services.order_executor import OrderExecutor

from services.correlation_context import (
    correlation_scope,
    get_correlation_id
)


logger = logging.getLogger("broker.orders")


class OrderProcessor:
    """
    Coordinates persistent stock orders.

    All modifying operations must be called by one
    worker at a time.
    """

    def __init__(self, repository, gateway, executor=None):

        self._repository = repository
        self._gateway = gateway

        self._executor = (
            executor if executor is not None
            else OrderExecutor()
        )

        self._customers, self._orders = repository.load()

    def submit(self, order):

        if not isinstance(order, Order):
            raise ValueError("Invalid order.")

        if order.username not in self._customers:
            raise ValueError(
                "Order refused: customer does not exist."
            )

        if order.order_id in self._orders:
            raise ValueError(
                "Order refused: duplicate order ID."
            )

        order.ensure_executable()

        saved_order = Order.from_record(
            order.to_record()
        )

        updated_orders = self._orders.copy()
        updated_orders[saved_order.order_id] = saved_order

        # Persist before accepting the new state.
        self._repository.save(
            self._customers,
            updated_orders
        )

        self._orders = updated_orders

        logger.info(
            "Order accepted: correlation_id=%s "
            "order_id=%s symbol=%s side=%s "
            "quantity=%s status=%s",
            saved_order.correlation_id,
            saved_order.order_id,
            saved_order.symbol,
            saved_order.side,
            saved_order.quantity,
            saved_order.status
        )

        return saved_order.to_record()

    def process(self, order_id):

        order = self._orders.get(order_id)

        if order is None:
            raise ValueError("Order not found.")

        # Restore the original correlation context,
        # including after a server restart.
        with correlation_scope(order.correlation_id):

            return self._execute_order(order)

    def _execute_order(self, order):

        # Completed orders are never executed twice.
        if order.is_terminal:

            logger.info(
                "Order execution skipped: "
                "correlation_id=%s order_id=%s status=%s",
                order.correlation_id,
                order.order_id,
                order.status
            )

            return order.to_record()

        logger.info(
            "Order execution started: "
            "correlation_id=%s order_id=%s",
            order.correlation_id,
            order.order_id
        )

        try:

            # The gateway automatically receives
            # the restored correlation context.
            price_cents = self._gateway.get_price(
                order.symbol
            )

            customer = self._customers[order.username]

            updated_customer, updated_order = (
                self._executor.execute(
                    order,
                    customer,
                    price_cents
                )
            )

            updated_customers = self._customers.copy()

            updated_customers[order.username] = (
                updated_customer
            )

            updated_orders = self._orders.copy()

            updated_orders[order.order_id] = (
                updated_order
            )

            # Portfolio and order status are saved together.
            self._repository.save(
                updated_customers,
                updated_orders
            )

            # Update memory only after persistence succeeds.
            self._customers = updated_customers
            self._orders = updated_orders

        except Exception as error:

            logger.error(
                "Order execution failed: "
                "correlation_id=%s order_id=%s "
                "error_type=%s",
                order.correlation_id,
                order.order_id,
                type(error).__name__
            )

            # Preserve the existing recovery behaviour.
            raise

        log_method = (
            logger.info
            if updated_order.status == "FILLED"
            else logger.warning
        )

        log_method(
            "Order execution completed: "
            "correlation_id=%s order_id=%s "
            "symbol=%s side=%s quantity=%s status=%s",
            updated_order.correlation_id,
            updated_order.order_id,
            updated_order.symbol,
            updated_order.side,
            updated_order.quantity,
            updated_order.status
        )

        return updated_order.to_record()

    def cancel(self, order_id):

        order = self._orders.get(order_id)

        if order is None:
            raise ValueError("Order not found.")

        updated_order = Order.from_record(
            order.to_record()
        )

        updated_order.cancel()

        updated_orders = self._orders.copy()
        updated_orders[order_id] = updated_order

        self._repository.save(
            self._customers,
            updated_orders
        )

        self._orders = updated_orders

        logger.info(
            "Order cancelled: "
            "correlation_id=%s "
            "original_correlation_id=%s "
            "order_id=%s status=%s",
            get_correlation_id() or order.correlation_id,
            order.correlation_id,
            order_id,
            updated_order.status
        )

        return updated_order.to_record()

    def get_order(self, order_id):

        order = self._orders.get(order_id)

        if order is None:
            raise ValueError("Order not found.")

        return order.to_record()

    def pending_order_ids(self):

        return [
            order_id
            for order_id, order in self._orders.items()
            if not order.is_terminal
        ]

    def register_customer(self, username, password):

        if username in self._customers:
            raise ValueError(
                "Registration refused: username already exists."
            )

        customer = CustomerAccount(username, password)

        if customer.username in self._customers:
            raise ValueError(
                "Registration refused: username already exists."
            )

        updated_customers = self._customers.copy()
        updated_customers[customer.username] = customer

        self._repository.save(
            updated_customers,
            self._orders
        )

        self._customers = updated_customers

        return {"username": customer.username}

    def authenticate_customer(self, username, password):

        customer = self._customers.get(username)

        if customer is None or not customer.authenticate(password):
            raise ValueError(
                "Login refused: invalid username or password."
            )

        return customer.username

    def get_customer_portfolio(self, username):

        customer = self._customers.get(username)

        if customer is None:
            raise ValueError("Customer not found.")

        return customer.get_portfolio()

    def get_statistics(self):

        portfolios = [
            customer.get_portfolio()
            for customer in self._customers.values()
        ]

        total_cash = sum(
            portfolio["cash_cents"]
            for portfolio in portfolios
        )

        total_shares = sum(
            position["shares"]
            for portfolio in portfolios
            for position in portfolio["holdings"].values()
        )

        return {
            "customer_count": len(self._customers),
            "total_cash_cents": total_cash,
            "total_shares": total_shares
        }