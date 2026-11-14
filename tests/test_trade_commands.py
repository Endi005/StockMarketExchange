
import unittest
from unittest.mock import Mock

from services.trade_commands import (
    TradeCommand,
    BuyStockCommand,
    SellStockCommand
)


class TestTradeCommands(unittest.TestCase):

    def setUp(self):
        self.portfolio = Mock()

    def test_buy_command(self):
        command = BuyStockCommand("AAPL", 2, 20000)

        command.execute(self.portfolio)

        self.portfolio.buy.assert_called_once_with(
            "AAPL", 2, 20000
        )

    def test_sell_command(self):
        command = SellStockCommand("AAPL", 1, 21000)

        command.execute(self.portfolio)

        self.portfolio.sell.assert_called_once_with(
            "AAPL", 1, 21000
        )

    def test_command_returns_portfolio_result(self):
        expected = {"shares": 2}
        self.portfolio.buy.return_value = expected

        command = BuyStockCommand("AAPL", 2, 20000)

        result = command.execute(self.portfolio)

        self.assertEqual(result, expected)

    def test_polymorphism(self):
        commands = [
            BuyStockCommand("AAPL", 2, 20000),
            SellStockCommand("AAPL", 1, 21000)
        ]

        for command in commands:
            self.assertIsInstance(command, TradeCommand)
            command.execute(self.portfolio)

        self.portfolio.buy.assert_called_once()
        self.portfolio.sell.assert_called_once()

    def test_abstract_class_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            TradeCommand("AAPL", 2, 20000)


if __name__ == "__main__":
    unittest.main()
