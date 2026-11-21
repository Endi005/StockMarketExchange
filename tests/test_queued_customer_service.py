
import unittest
from unittest.mock import Mock

from services.queued_customer_service import QueuedCustomerService


class TestQueuedCustomerService(unittest.TestCase):

    def setUp(self):
        self.queue = Mock()

        self.queue.authenticate_customer.return_value = "Frank"
        self.queue.register_customer.return_value = {
            "username": "Emma"
        }

        self.queue.submit.side_effect = (
            lambda order: order.to_record()
        )

        self.queue.get_order.return_value = {
            "order_id": "order123",
            "username": "Frank",
            "status": "PENDING"
        }

        self.queue.cancel.return_value = {
            "order_id": "order123",
            "status": "CANCELLED"
        }

        self.service = QueuedCustomerService(self.queue)
        self.token = self.service.login(
            "Frank", "password123"
        )

    def test_registration(self):
        result = self.service.register(
            "Emma", "password456"
        )

        self.assertEqual(result["username"], "Emma")

        self.queue.register_customer.assert_called_once_with(
            "Emma", "password456"
        )

    def test_login_creates_session(self):
        self.assertIsInstance(self.token, str)
        self.assertEqual(
            self.service.get_username(self.token),
            "Frank"
        )

    def test_invalid_session_rejected(self):
        with self.assertRaises(ValueError):
            self.service.get_portfolio("invalid-token")

        self.queue.get_customer_portfolio.assert_not_called()

    def test_logout_invalidates_session(self):
        self.service.logout(self.token)

        with self.assertRaises(ValueError):
            self.service.get_username(self.token)

    def test_portfolio_request(self):
        self.queue.get_customer_portfolio.return_value = {
            "cash_cents": 100000,
            "holdings": {}
        }

        result = self.service.get_portfolio(self.token)

        self.assertEqual(result["cash_cents"], 100000)

        self.queue.get_customer_portfolio.assert_called_once_with(
            "Frank"
        )

    def test_buy_creates_pending_order(self):
        result = self.service.buy_stock(
            self.token, "AAPL", 2
        )

        self.assertEqual(result["username"], "Frank")
        self.assertEqual(result["symbol"], "AAPL")
        self.assertEqual(result["side"], "buy")
        self.assertEqual(result["quantity"], 2)
        self.assertEqual(result["status"], "PENDING")

        self.queue.submit.assert_called_once()

    def test_sell_creates_pending_order(self):
        result = self.service.sell_stock(
            self.token, "AAPL", 1
        )

        self.assertEqual(result["side"], "sell")
        self.assertEqual(result["quantity"], 1)
        self.assertEqual(result["status"], "PENDING")

    def test_customer_can_view_own_order(self):
        result = self.service.get_order(
            self.token, "order123"
        )

        self.assertEqual(result["username"], "Frank")

    def test_customer_cannot_view_another_order(self):
        self.queue.get_order.return_value = {
            "order_id": "order456",
            "username": "Emma",
            "status": "PENDING"
        }

        with self.assertRaises(ValueError):
            self.service.get_order(
                self.token, "order456"
            )

    def test_customer_cannot_cancel_another_order(self):
        self.queue.get_order.return_value = {
            "order_id": "order456",
            "username": "Emma",
            "status": "PENDING"
        }

        with self.assertRaises(ValueError):
            self.service.cancel_order(
                self.token, "order456"
            )

        self.queue.cancel.assert_not_called()

    def test_cancel_own_order(self):
        result = self.service.cancel_order(
            self.token, "order123"
        )

        self.assertEqual(result["status"], "CANCELLED")
        self.queue.cancel.assert_called_once_with(
            "order123"
        )


if __name__ == "__main__":
    unittest.main()
