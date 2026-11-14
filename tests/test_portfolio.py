import unittest
from models.portfolio import Portfolio


class TestPortfolio(unittest.TestCase):

    def setUp(self):
        self.portfolio = Portfolio(100000)

    def test_initial_balance(self):
        summary = self.portfolio.get_summary()
        self.assertEqual(summary["cash_cents"], 100000)