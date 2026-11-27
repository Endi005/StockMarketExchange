from services.price_observer import PriceObserver


class PriceHistoryObserver(PriceObserver):
    """Records market price changes in a history dictionary."""

    def __init__(self, history):
        self._history = history

    def on_price_changed(self, symbol, new_price):
        self._history.setdefault(symbol, []).append(new_price)