
import unittest

from models.order_state import (
    PendingState,
    FilledState,
    RejectedState,
    CancelledState,
    state_from_name
)


class TestOrderState(unittest.TestCase):

    def test_pending_order_can_execute(self):
        state = PendingState()

        self.assertTrue(state.ensure_executable())
        self.assertFalse(state.is_terminal)

    def test_pending_can_be_filled(self):
        state = PendingState()
        next_state = state.fill()

        self.assertIsInstance(next_state, FilledState)
        self.assertEqual(next_state.name, "FILLED")

    def test_pending_can_be_rejected(self):
        state = PendingState()
        next_state = state.reject()

        self.assertIsInstance(next_state, RejectedState)
        self.assertEqual(next_state.name, "REJECTED")

    def test_pending_can_be_cancelled(self):
        state = PendingState()
        next_state = state.cancel()

        self.assertIsInstance(next_state, CancelledState)
        self.assertEqual(next_state.name, "CANCELLED")

    def test_terminal_states_cannot_execute(self):
        states = [
            FilledState(),
            RejectedState(),
            CancelledState()
        ]

        for state in states:
            with self.subTest(state=state.name):
                self.assertTrue(state.is_terminal)

                with self.assertRaises(ValueError):
                    state.ensure_executable()

    def test_terminal_states_cannot_transition(self):
        states = [
            FilledState(),
            RejectedState(),
            CancelledState()
        ]

        for state in states:
            with self.subTest(state=state.name):
                with self.assertRaises(ValueError):
                    state.fill()

                with self.assertRaises(ValueError):
                    state.reject()

                with self.assertRaises(ValueError):
                    state.cancel()

    def test_restore_saved_state(self):
        for name in (
            "PENDING",
            "FILLED",
            "REJECTED",
            "CANCELLED"
        ):
            with self.subTest(name=name):
                state = state_from_name(name)
                self.assertEqual(state.name, name)

    def test_invalid_saved_state_rejected(self):
        for name in ("UNKNOWN", "", None, 123):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    state_from_name(name)


if __name__ == "__main__":
    unittest.main()
