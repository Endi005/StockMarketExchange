
import threading

from models.stock import Stock


class ExchangeService:

    def __init__(self, stocks, repository=None):
        self._repository = repository
        self._lock = threading.RLock()
        self._stocks = {}
        self._history = {}

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
                self._history[symbol] = list(record["history"])

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

    def update_price(self, symbol, new_price):
        with self._lock:
            stock = self._find_stock(symbol)

            updated_stock = Stock(
                stock.name,
                stock.symbol,
                new_price
            )

            snapshot = self._snapshot()
            record = snapshot["stocks"][stock.symbol]

            record["price_cents"] = updated_stock.get_price()
            record["history"].append(
                updated_stock.get_price()
            )

            if self._repository is not None:
                self._repository.save(snapshot)

            self._stocks[stock.symbol] = updated_stock
            self._history[stock.symbol] = record["history"]

    def simulate_tick(self):
        with self._lock:
            snapshot = self._snapshot()

            for symbol, record in snapshot["stocks"].items():
                current = record["price_cents"]
                change = max(1, current // 100)

                if len(record["history"]) % 2 == 1:
                    new_price = current + change
                else:
                    new_price = max(1, current - change)

                record["price_cents"] = new_price
                record["history"].append(new_price)

            if self._repository is not None:
                self._repository.save(snapshot)

            for symbol, record in snapshot["stocks"].items():
                self._stocks[symbol] = Stock(
                    record["name"],
                    symbol,
                    record["price_cents"]
                )
                self._history[symbol] = record["history"]

            return self.get_prices()

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
