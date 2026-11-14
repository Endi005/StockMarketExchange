
import unittest

from models.customer import CustomerAccount


class TestCustomerAccount(unittest.TestCase):

    def test_create_customer(self):
        customer = CustomerAccount("John", "password123")

        self.assertEqual(customer.username, "John")

    def test_correct_password(self):
        customer = CustomerAccount("John", "password123")

        self.assertTrue(customer.authenticate("password123"))

    def test_wrong_password(self):
        customer = CustomerAccount("John", "password123")

        self.assertFalse(customer.authenticate("wrongpass"))

    def test_independent_portfolios(self):
        john = CustomerAccount("John", "password123")
        emma = CustomerAccount("Emma", "password456")

        emma.portfolio.buy("AAPL", 2, 20000)

        self.assertEqual(
            john.get_portfolio()["cash_cents"], 100000
        )

        self.assertEqual(
            emma.get_portfolio()["cash_cents"], 60000
        )


if __name__ == "__main__":
    unittest.main()
