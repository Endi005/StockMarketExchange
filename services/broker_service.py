
import threading

from models.portfolio import Portfolio


class BrokerService:

    def __init__(self, gateway, portfolio=None, repository=None):
        self._gateway = gateway
        self._repository = repository
        self._lock = threading.RLock()

        if portfolio is not None and repository is not None:
            raise ValueError(
                "Provide either a portfolio or a repository."
            )

        saved_data = None

        if repository is not None:
            saved_data = repository.load()

        if saved_data is not None:
            self._portfolio = Portfolio.from_snapshot(saved_data)
        elif portfolio is not None:
            self._portfolio = portfolio
        else:
            self._portfolio = Portfolio()

    def get_prices(self):
        return self._gateway.get_prices()

    def get_price(self, symbol):
        return self._gateway.get_price(symbol)

    def buy_stock(self, symbol, quantity):
        with self._lock:
            price = self._gateway.get_price(symbol)

            updated = Portfolio.from_snapshot(
                self._portfolio.get_summary()
            )

            result = updated.buy(symbol, quantity, price)
            self._commit(updated)

            return result

    def sell_stock(self, symbol, quantity):
        with self._lock:
            price = self._gateway.get_price(symbol)

            updated = Portfolio.from_snapshot(
                self._portfolio.get_summary()
            )

            result = updated.sell(symbol, quantity, price)
            self._commit(updated)

            return result

    def get_portfolio(self):
        with self._lock:
            return self._portfolio.get_summary()

    def _commit(self, updated_portfolio):
        if self._repository is not None:
            self._repository.save(
                updated_portfolio.get_summary()
            )

        self._portfolio = updated_portfolio
