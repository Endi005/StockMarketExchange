
import json
import tempfile
import unittest
from pathlib import Path

from models.customer import CustomerAccount
from repositories.customer_repository import CustomerRepository


class TestCustomerRepository(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.file_path = Path(self.directory.name) / "customers.json"
        self.repository = CustomerRepository(self.file_path)

    def test_missing_file_returns_empty_accounts(self):
        self.assertEqual(self.repository.load(), {})

    def test_save_and_restore_customers(self):
        john = CustomerAccount("John", "password123")
        emma = CustomerAccount("Emma", "password456")

        emma.portfolio.buy("AAPL", 2, 20000)

        self.repository.save({
            "John": john,
            "Emma": emma
        })

        restored = self.repository.load()

        self.assertEqual(len(restored), 2)
        self.assertTrue(
            restored["John"].authenticate("password123")
        )
        self.assertTrue(
            restored["Emma"].authenticate("password456")
        )
        self.assertEqual(
            restored["Emma"].get_portfolio()["cash_cents"],
            60000
        )
        self.assertEqual(
            restored["John"].get_portfolio()["cash_cents"],
            100000
        )

    def test_invalid_data_is_rejected(self):
        self.file_path.write_text(
            json.dumps({"John": {"invalid": "data"}}),
            encoding="utf-8"
        )

        with self.assertRaises(ValueError):
            self.repository.load()


if __name__ == "__main__":
    unittest.main()
