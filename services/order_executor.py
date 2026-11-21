
from models.customer import CustomerAccount
from models.order import Order
from services.trade_commands import (
    BuyStockCommand,
    SellStockCommand
)


class OrderExecutor:
    """Executes an order without modifying original objects."""

    def execute(self, order, customer, price_cents):
        if not isinstance(order, Order):
            raise ValueError("Invalid order object.")

        if not isinstance(customer, CustomerAccount):
            raise ValueError("Invalid customer object.")

        if order.username != customer.username:
            raise ValueError(
                "Order customer does not match account."
            )

        order.ensure_executable()

        if type(price_cents) is not int or price_cents <= 0:
            raise ValueError("Invalid execution price.")

        updated_customer = CustomerAccount.from_record(
            customer.to_record()
        )

        updated_order = Order.from_record(
            order.to_record()
        )

        command_types = {
            "buy": BuyStockCommand,
            "sell": SellStockCommand
        }

        command_type = command_types[order.side]

        command = command_type(
            order.symbol,
            order.quantity,
            price_cents
        )

        try:
            result = command.execute(
                updated_customer.portfolio
            )

        except ValueError as error:
            updated_order.reject(str(error))
            return updated_customer, updated_order

        updated_order.fill(price_cents, result)

        return updated_customer, updated_order
