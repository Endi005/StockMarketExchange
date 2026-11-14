
class Portfolio:

    def __init__(self, cash_cents=100000):
        if type(cash_cents) is not int or cash_cents < 0:
            raise ValueError("Starting cash must be non-negative.")

        self._cash_cents = cash_cents
        self._holdings = {}

    def buy(self, symbol, quantity, price_cents):
        symbol = self._validate_order(symbol, quantity, price_cents)
        cost = quantity * price_cents

        if cost > self._cash_cents:
            raise ValueError(
                "Purchase refused: insufficient funds. "
                "Buy fewer shares."
            )

        position = self._holdings.get(
            symbol, {"shares": 0, "total_paid_cents": 0}
        )

        self._cash_cents -= cost
        position["shares"] += quantity
        position["total_paid_cents"] += cost
        self._holdings[symbol] = position

        return {"symbol": symbol, "shares": quantity, "cost_cents": cost}

    def sell(self, symbol, quantity, price_cents):
        symbol = self._validate_order(symbol, quantity, price_cents)
        position = self._holdings.get(symbol)

        if position is None or position["shares"] < quantity:
            raise ValueError(
                "Sale refused: not enough shares. "
                "Check your portfolio."
            )

        proceeds = quantity * price_cents
        old_shares = position["shares"]

        if quantity == old_shares:
            del self._holdings[symbol]
        else:
            removed_cost = (
                position["total_paid_cents"] * quantity // old_shares
            )
            position["shares"] -= quantity
            position["total_paid_cents"] -= removed_cost

        self._cash_cents += proceeds

        return {
            "symbol": symbol,
            "shares": quantity,
            "proceeds_cents": proceeds
        }

    def get_summary(self):
        return {
            "cash_cents": self._cash_cents,
            "holdings": {
                symbol: position.copy()
                for symbol, position in self._holdings.items()
            }
        }

    @staticmethod
    def _validate_order(symbol, quantity, price_cents):
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Enter a valid stock symbol.")

        if type(quantity) is not int or quantity <= 0:
            raise ValueError("Quantity must be a positive integer.")

        if type(price_cents) is not int or price_cents <= 0:
            raise ValueError("Price must be a positive integer.")

        return symbol.strip().upper()
    
    @classmethod
    def from_snapshot(cls, snapshot):
        if not isinstance(snapshot, dict):
            raise ValueError("Invalid portfolio snapshot.")

        if set(snapshot) != {"cash_cents", "holdings"}:
            raise ValueError("Invalid portfolio data.")

        cash = snapshot["cash_cents"]
        holdings = snapshot["holdings"]

        if type(cash) is not int or cash < 0:
            raise ValueError("Invalid cash balance.")

        if not isinstance(holdings, dict):
            raise ValueError("Invalid holdings.")

        portfolio = cls(cash)

        for symbol, position in holdings.items():
            if (
                not isinstance(symbol, str)
                or not symbol
                or symbol != symbol.strip().upper()
                or not isinstance(position, dict)
                or set(position) != {"shares", "total_paid_cents"}
            ):
                raise ValueError("Invalid saved position.")

            shares = position["shares"]
            paid = position["total_paid_cents"]

            if (
                type(shares) is not int or shares <= 0
                or type(paid) is not int or paid < 0
            ):
                raise ValueError("Invalid saved share data.")

            portfolio._holdings[symbol] = position.copy()

        return portfolio

