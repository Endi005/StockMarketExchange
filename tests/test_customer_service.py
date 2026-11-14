
import tempfile
import unittest
from pathlib import Path

from services.customer_service import CustomerService
from repositories.customer_repository import CustomerRepository


class TestCustomerService(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        path = Path(self.directory.name) / "customers.json"
        self.repository = CustomerRepository(path)
        self.service = CustomerService(self.repository)

    def test_register_customer(self):
        result = self.service.register("Emma", "password123")
        self.assertEqual(result["username"], "Emma")
        self.assertIn("Emma", self.repository.load())

    def test_login(self):
        self.service.register("Emma", "password123")
        token = self.service.login("Emma", "password123")

        self.assertEqual(
            self.service.get_username(token), "Emma"
        )

    def test_wrong_password(self):
        self.service.register("Emma", "password123")

        with self.assertRaises(ValueError):
            self.service.login("Emma", "wrongpassword")

    def test_duplicate_username(self):
        self.service.register("Emma", "password123")

        with self.assertRaises(ValueError):
            self.service.register("Emma", "anotherpass")

    def test_logout(self):
        self.service.register("Emma", "password123")
        token = self.service.login("Emma", "password123")

        self.assertTrue(self.service.logout(token))

        with self.assertRaises(ValueError):
            self.service.get_username(token)


if __name__ == "__main__":
    unittest.main()

