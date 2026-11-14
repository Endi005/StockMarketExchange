
from abc import ABC, abstractmethod


class TradeCommand(ABC):
    """Base class for stock trading commands."""

    def __init__(self, symbol, quantity, price_cents):
        self.symbol = symbol
        self.quantity = quantity
        self.price_cents = price_cents

    @abstractmethod
    def execute(self, portfolio):
        """Execute the command on a portfolio."""
        pass


class BuyStockCommand(TradeCommand):
    """Command for purchasing shares."""

    def execute(self, portfolio):
        return portfolio.buy(
            self.symbol,
            self.quantity,
            self.price_cents
        )


class SellStockCommand(TradeCommand):
    """Command for selling shares."""

    def execute(self, portfolio):
        return portfolio.sell(
            self.symbol,
            self.quantity,
            self.price_cents
        )
