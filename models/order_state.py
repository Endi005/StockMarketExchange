
class OrderState:
    """Base class defining valid order transitions."""

    name = "UNKNOWN"
    is_terminal = True

    def ensure_executable(self):
        raise ValueError(
            f"Order is {self.name}. It cannot be executed again."
        )

    def fill(self):
        raise ValueError(
            f"Order is {self.name}. Cannot fill this order."
        )

    def reject(self):
        raise ValueError(
            f"Order is {self.name}. Cannot reject this order."
        )

    def cancel(self):
        raise ValueError(
            f"Order is {self.name}. Cannot cancel this order."
        )


class PendingState(OrderState):
    name = "PENDING"
    is_terminal = False

    def ensure_executable(self):
        return True

    def fill(self):
        return FilledState()

    def reject(self):
        return RejectedState()

    def cancel(self):
        return CancelledState()


class FilledState(OrderState):
    name = "FILLED"


class RejectedState(OrderState):
    name = "REJECTED"


class CancelledState(OrderState):
    name = "CANCELLED"


def state_from_name(name):
    """Reconstruct an order state from saved data."""

    state_types = {
        "PENDING": PendingState,
        "FILLED": FilledState,
        "REJECTED": RejectedState,
        "CANCELLED": CancelledState
    }

    if type(name) is not str or name not in state_types:
        raise ValueError("Invalid saved order state.")

    return state_types[name]()
