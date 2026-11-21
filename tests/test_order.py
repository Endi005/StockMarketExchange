
import unittest

from models.order import Order


class TestOrder(unittest.TestCase):

    def setUp(self):
        self.order = Order("Frank", "AAPL", "buy", 2)

    def test_new_order_is_pending(self):
        self.assertEqual(self.order.status, "PENDING")
        self.assertFalse(self.order.is_terminal)
        self.assertEqual(len(self.order.order_id), 32)
        self.assertEqual(
            self.order.to_record()["history"],
            ["PENDING"]
        )

    def test_unique_order_ids(self):
        second_order = Order("Frank", "AAPL", "buy", 2)

        self.assertNotEqual(
            self.order.order_id,
            second_order.order_id
        )

    def test_fill_buy_order(self):
        result = {
            "symbol": "AAPL",
            "shares": 2,
            "cost_cents": 40000
        }

        self.order.fill(20000, result)

        self.assertEqual(self.order.status, "FILLED")
        self.assertTrue(self.order.is_terminal)
        self.assertEqual(
            self.order.to_record()["history"],
            ["PENDING", "FILLED"]
        )

    def test_fill_sell_order(self):
        order = Order("Frank", "AAPL", "sell", 1)

        result = {
            "symbol": "AAPL",
            "shares": 1,
            "proceeds_cents": 21000
        }

        order.fill(21000, result)

        self.assertEqual(order.status, "FILLED")

    def test_reject_order(self):
        self.order.reject("Insufficient funds.")

        self.assertEqual(self.order.status, "REJECTED")
        self.assertTrue(self.order.is_terminal)
        self.assertEqual(
            self.order.to_record()["error"],
            "Insufficient funds."
        )

    def test_cancel_order(self):
        self.order.cancel()

        self.assertEqual(self.order.status, "CANCELLED")
        self.assertTrue(self.order.is_terminal)

    def test_completed_order_cannot_execute_again(self):
        self.order.fill(
            20000,
            {
                "symbol": "AAPL",
                "shares": 2,
                "cost_cents": 40000
            }
        )

        with self.assertRaises(ValueError):
            self.order.ensure_executable()

        with self.assertRaises(ValueError):
            self.order.cancel()

    def test_invalid_result_is_rejected(self):
        with self.assertRaises(ValueError):
            self.order.fill(
                20000,
                {
                    "symbol": "AAPL",
                    "shares": 2,
                    "cost_cents": 100
                }
            )

        self.assertEqual(self.order.status, "PENDING")

    def test_save_and_restore_order(self):
        self.order.fill(
            20000,
            {
                "symbol": "AAPL",
                "shares": 2,
                "cost_cents": 40000
            }
        )

        saved = self.order.to_record()
        restored = Order.from_record(saved)

        self.assertEqual(restored.order_id, self.order.order_id)
        self.assertEqual(restored.status, "FILLED")
        self.assertEqual(restored.to_record(), saved)

    def test_restore_rejects_corrupted_history(self):
        saved = self.order.to_record()
        saved["history"] = ["PENDING", "FILLED"]

        with self.assertRaises(ValueError):
            Order.from_record(saved)

    def test_invalid_quantity_rejected(self):
        with self.assertRaises(ValueError):
            Order("Frank", "AAPL", "buy", -1)

    def test_invalid_order_side_rejected(self):
        with self.assertRaises(ValueError):
            Order("Frank", "AAPL", "hold", 2)


if __name__ == "__main__":
    unittest.main()
