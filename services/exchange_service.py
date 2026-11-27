import logging
import threading

from models.stock import Stock
from services.price_history_observer import PriceHistoryObserver


logger = logging.getLogger("exchange.market")


class ExchangeService:
    """Manages market prices, history and price-change observers."""

    def __init__(self, stocks, repository=None):
        self._repository = repository

        self._lock = threading.RLock()
        self._update_lock = threading.Lock()

        self._stocks = {}
        self._history = {}
        self._observers = []

        saved_data = (
            repository.load()
            if repository is not None
            else None
        )

        if saved_data is not None:
            for symbol, record in saved_data["stocks"].items():
                self._stocks[symbol] = Stock(
                    record["name"],
                    symbol,
                    record["price_cents"]
                )

                self._history[symbol] = list(
                    record["history"]
                )

        else:
            for stock in stocks:
                if stock.symbol in self._stocks:
                    raise ValueError("Duplicate stock symbol.")

                self._stocks[stock.symbol] = stock

                self._history[stock.symbol] = [
                    stock.get_price()
                ]

            if not self._stocks:
                raise ValueError("Exchange requires stocks.")

            if repository is not None:
                repository.save(self._snapshot())

    def add_observer(self, observer):
        if not callable(
            getattr(observer, "on_price_changed", None)
        ):
            raise ValueError("Invalid price observer.")

        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)

    def remove_observer(self, observer):
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)

    def _notify_observers(self, events):
        with self._lock:
            observers = list(self._observers)

        for symbol, new_price in events:
            for observer in observers:
                try:
                    observer.on_price_changed(
                        symbol, new_price
                    )

                except Exception:
                    logger.exception(
                        "Price observer failed: "
                        "observer=%s symbol=%s price=%s",
                        type(observer).__name__,
                        symbol,
                        new_price
                    )

    def get_prices(self):
        with self._lock:
            return {
                symbol: stock.get_price()
                for symbol, stock in self._stocks.items()
            }

    def get_price(self, symbol):
        with self._lock:
            return self._find_stock(symbol).get_price()

    def get_history(self, symbol):
        with self._lock:
            stock = self._find_stock(symbol)

            return list(self._history[stock.symbol])

    def _prepare_price_change(
        self, snapshot, symbol, new_price
    ):
        record = snapshot["stocks"][symbol]

        updated_stock = Stock(
            record["name"],
            symbol,
            new_price
        )

        temporary_history = {
            key: item["history"]
            for key, item in snapshot["stocks"].items()
        }

        history_observer = PriceHistoryObserver(
            temporary_history
        )

        history_observer.on_price_changed(
            symbol,
            updated_stock.get_price()
        )

        record["price_cents"] = updated_stock.get_price()

    def _commit_snapshot(self, snapshot):
        updated_stocks = {}
        updated_history = {}

        for symbol, record in snapshot["stocks"].items():
            updated_stocks[symbol] = Stock(
                record["name"],
                symbol,
                record["price_cents"]
            )

            updated_history[symbol] = record["history"]

        if self._repository is not None:
            self._repository.save(snapshot)

        with self._lock:
            self._stocks = updated_stocks
            self._history = updated_history

    def update_price(self, symbol, new_price):
        with self._update_lock:
            with self._lock:
                stock = self._find_stock(symbol)
                symbol = stock.symbol
                snapshot = self._snapshot()

            self._prepare_price_change(
                snapshot,
                symbol,
                new_price
            )

            self._commit_snapshot(snapshot)

            committed_price = snapshot["stocks"][
                symbol
            ]["price_cents"]

        self._notify_observers([
            (symbol, committed_price)
        ])

    def simulate_tick(self):
        events = []

        with self._update_lock:
            with self._lock:
                snapshot = self._snapshot()

            for symbol, record in snapshot["stocks"].items():
                current = record["price_cents"]
                change = max(1, current // 100)

                if len(record["history"]) % 2 == 1:
                    new_price = current + change
                else:
                    new_price = max(1, current - change)

                self._prepare_price_change(
                    snapshot,
                    symbol,
                    new_price
                )

                events.append((symbol, new_price))

            self._commit_snapshot(snapshot)

            prices = {
                symbol: record["price_cents"]
                for symbol, record in snapshot["stocks"].items()
            }

        self._notify_observers(events)

        return prices

    def get_statistics(self):
        with self._lock:
            return {
                "stock_count": len(self._stocks),
                "prices": self.get_prices(),
                "history_entries": {
                    symbol: len(history)
                    for symbol, history in self._history.items()
                }
            }

    def _snapshot(self):
        return {
            "stocks": {
                symbol: {
                    "name": stock.name,
                    "price_cents": stock.get_price(),
                    "history": list(self._history[symbol])
                }
                for symbol, stock in self._stocks.items()
            }
        }

    def _find_stock(self, symbol):
        if not isinstance(symbol, str):
            raise ValueError("Stock symbol must be text.")

        symbol = symbol.strip().upper()

        if symbol not in self._stocks:
            raise ValueError(
                "Stock not found. Check the symbol."
            )

        return self._stocks[symbol]