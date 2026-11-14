
class ExchangeService:

    def __init__(self, stocks):
        self._stocks = {}
        self._history = {}

        for stock in stocks:
            if stock.symbol in self._stocks:
                raise ValueError("Duplicate stock symbol.")

            self._stocks[stock.symbol] = stock
            self._history[stock.symbol] = [stock.get_price()]

    def get_prices(self):
        return {
            symbol: stock.get_price()
            for symbol, stock in self._stocks.items()
        }

    def get_price(self, symbol):
        stock = self._find_stock(symbol)
        return stock.get_price()

    def update_price(self, symbol, new_price):
        stock = self._find_stock(symbol)
        stock.update_price(new_price)
        self._history[stock.symbol].append(new_price)

    def get_history(self, symbol):
        stock = self._find_stock(symbol)
        return list(self._history[stock.symbol])

    def _find_stock(self, symbol):
        if not isinstance(symbol, str):
            raise ValueError("Stock symbol must be text.")

        symbol = symbol.strip().upper()

        if symbol not in self._stocks:
            raise ValueError("Stock not found.")

        return self._stocks[symbol]

