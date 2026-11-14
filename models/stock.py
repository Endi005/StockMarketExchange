
class Stock:
    def __init__(self, name, symbol, price_cents):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Stock name cannot be empty.")

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Stock symbol cannot be empty.")

        self.name = name.strip()
        self.symbol = symbol.strip().upper()
        self._price_cents = 0
        self.update_price(price_cents)

    def get_price(self):
        return self._price_cents

    def update_price(self, new_price_cents):
        if type(new_price_cents) is not int or new_price_cents <= 0:
            raise ValueError("Price must be a positive integer in cents.")

        self._price_cents = new_price_cents
