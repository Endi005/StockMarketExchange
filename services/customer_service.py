
import secrets
import threading

from models.customer import CustomerAccount


class CustomerService:

    def __init__(self, repository, gateway=None):
        self._repository = repository
        self._gateway = gateway
        self._customers = repository.load()
        self._sessions = {}
        self._lock = threading.RLock()

    def register(self, username, password):
        with self._lock:
            customer = CustomerAccount(username, password)

            if customer.username in self._customers:
                raise ValueError(
                    "Registration refused: username already exists. "
                    "Choose another username."
                )

            updated = self._customers.copy()
            updated[customer.username] = customer

            self._repository.save(updated)
            self._customers = updated

            return {"username": customer.username}

    def login(self, username, password):
        with self._lock:
            customer = self._customers.get(username)

            if customer is None or not customer.authenticate(password):
                raise ValueError(
                    "Login refused: invalid username or password. "
                    "Check your credentials."
                )

            token = secrets.token_urlsafe(32)
            self._sessions[token] = username

            return token

    def get_username(self, token):
        with self._lock:
            if not isinstance(token, str) or token not in self._sessions:
                raise ValueError(
                    "Access refused: invalid session. Log in again."
                )

            return self._sessions[token]

    def logout(self, token):
        with self._lock:
            self.get_username(token)
            del self._sessions[token]
            return True

    def get_portfolio(self, token):
        with self._lock:
            username = self.get_username(token)
            return self._customers[username].get_portfolio()

    def buy_stock(self, token, symbol, quantity):
        return self._trade(token, symbol, quantity, "buy")

    def sell_stock(self, token, symbol, quantity):
        return self._trade(token, symbol, quantity, "sell")

    def _trade(self, token, symbol, quantity, action):
        with self._lock:
            username = self.get_username(token)

            if self._gateway is None:
                raise RuntimeError(
                    "Trading unavailable. Configure the exchange."
                )

            price = self._gateway.get_price(symbol)

            original = self._customers[username]
            updated_customer = CustomerAccount.from_record(
                original.to_record()
            )

            if action == "buy":
                result = updated_customer.portfolio.buy(
                    symbol, quantity, price
                )
            elif action == "sell":
                result = updated_customer.portfolio.sell(
                    symbol, quantity, price
                )
            else:
                raise ValueError("Invalid trading action.")

            updated_customers = self._customers.copy()
            updated_customers[username] = updated_customer

            self._repository.save(updated_customers)
            self._customers = updated_customers

            return result



    def get_statistics(self):
        with self._lock:
            portfolios = [
                customer.get_portfolio()
                for customer in self._customers.values()
            ]

            total_cash = sum(
                portfolio["cash_cents"]
                for portfolio in portfolios
            )

            total_shares = sum(
                position["shares"]
                for portfolio in portfolios
                for position in portfolio["holdings"].values()
            )

            return {
                "customer_count": len(self._customers),
                "total_cash_cents": total_cash,
                "total_shares": total_shares
            }
