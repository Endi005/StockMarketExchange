from models.customer import CustomerAccount
from models.order import Order
from services.order_executor import OrderExecutor


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

        return saved_order.to_record()

    def process(self, order_id):
        order = self._orders.get(order_id)

        if order is None:
            raise ValueError("Order not found.")

        # Completed orders are never executed twice.
        if order.is_terminal:
            return order.to_record()

        # The network request happens outside a state lock.
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
        updated_customers[order.username] = updated_customer

        updated_orders = self._orders.copy()
        updated_orders[order_id] = updated_order

        # Portfolio and order status are saved together.
        self._repository.save(
            updated_customers,
            updated_orders
        )

        # Update memory only after persistence succeeds.
        self._customers = updated_customers
        self._orders = updated_orders

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

        # Save customers together with all existing orders.
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

