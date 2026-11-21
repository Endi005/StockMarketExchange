
import json
import socket
from getpass import getpass


class CustomerClient:
    def __init__(self):
        self.host = "127.0.0.1"
        self.port = 9002
        self.session_token = None
        self.username = None
        self.last_order_id = None

    def send_request(self, action, **parameters):
        request = {"action": action, **parameters}

        if self.session_token is not None:
            request["session_token"] = self.session_token

        try:
            with socket.create_connection(
                (self.host, self.port), timeout=5
            ) as connection:
                connection.settimeout(5)

                with connection.makefile("rwb") as stream:
                    stream.write(
                        (json.dumps(request) + "\n").encode("utf-8")
                    )
                    stream.flush()
                    response_line = stream.readline(8192)

        except OSError as error:
            raise RuntimeError(
                "Broker unavailable. Check that it is running."
            ) from error

        if not response_line.endswith(b"\n"):
            raise RuntimeError("Incomplete response. Try again.")

        try:
            response = json.loads(response_line)

        except (ValueError, UnicodeError) as error:
            raise RuntimeError(
                "Invalid response from Broker Server."
            ) from error

        if not isinstance(response, dict):
            raise RuntimeError("Invalid server response.")

        if response.get("ok") is not True:
            raise RuntimeError(
                response.get("error", "Request failed.")
            )

        return response["data"]

    def register(self):
        print("\n=== REGISTER CUSTOMER ===")

        username = input("Choose username: ").strip()
        password = getpass(
            "Choose password (min 8 characters): "
        )

        result = self.send_request(
            "register",
            username=username,
            password=password
        )

        print(
            f"Account {result['username']} created successfully!"
        )
        print("You can now log in.")

    def login(self):
        print("\n=== CUSTOMER LOGIN ===")

        username = input("Username: ").strip()
        password = getpass("Password: ")

        result = self.send_request(
            "login",
            username=username,
            password=password
        )

        self.session_token = result["session_token"]
        self.username = username
        self.last_order_id = None

        print(f"Welcome, {username}!")

    def logout(self):
        self.send_request("logout")

        self.session_token = None
        self.username = None
        self.last_order_id = None

        print("Logged out successfully.")

    def show_prices(self):
        prices = self.send_request("get_prices")

        print("\n=== AVAILABLE STOCKS ===")

        for symbol, price in prices.items():
            print(f"{symbol}: ${price / 100:.2f}")

    def search_stock(self):
        symbol = input("Stock symbol: ").strip()

        price = self.send_request(
            "get_price",
            symbol=symbol
        )

        print(f"{symbol.upper()}: ${price / 100:.2f}")

    def _show_order(self, order):
        status = order["status"]

        print(f"\nOrder ID: {order['order_id']}")
        print(f"Status: {status}")

        if status == "PENDING":
            print("Your order is waiting to be processed.")

        elif status == "FILLED":
            result = order["result"]

            shares = result["shares"]
            symbol = result["symbol"]

            if order["side"] == "buy":
                amount = result["cost_cents"]

                print(
                    f"Bought {shares} {symbol} shares "
                    f"for ${amount / 100:.2f}"
                )

            else:
                amount = result["proceeds_cents"]

                print(
                    f"Sold {shares} {symbol} shares "
                    f"for ${amount / 100:.2f}"
                )

        elif status in ("REJECTED", "CANCELLED"):
            print(
                f"Reason: {order.get('error') or 'Not available'}"
            )

    def _place_order(self, side):
        symbol = input("Stock symbol: ").strip()
        quantity = int(input("Number of shares: "))

        order = self.send_request(
            side,
            symbol=symbol,
            quantity=quantity
        )

        self.last_order_id = order["order_id"]

        print("Order submitted successfully.")

        self._show_order(order)

        print(
            "Use 'Check order status' to see the final result."
        )

    def buy_stock(self):
        self._place_order("buy")

    def sell_stock(self):
        self._place_order("sell")

    def _ask_order_id(self):
        if self.last_order_id is None:
            order_id = input("Order ID: ").strip()

        else:
            print(f"Last order ID: {self.last_order_id}")

            order_id = input(
                "Order ID (Enter = last order): "
            ).strip()

            if not order_id:
                order_id = self.last_order_id

        if not order_id:
            raise ValueError("Enter a valid order ID.")

        return order_id

    def check_order_status(self):
        order_id = self._ask_order_id()

        order = self.send_request(
            "get_order",
            order_id=order_id
        )

        self._show_order(order)

    def cancel_order(self):
        order_id = self._ask_order_id()

        order = self.send_request(
            "cancel_order",
            order_id=order_id
        )

        self._show_order(order)

    def show_portfolio(self):
        portfolio = self.send_request("get_portfolio")

        print(f"\n=== {self.username}'s PORTFOLIO ===")

        print(
            f"Available cash: "
            f"${portfolio['cash_cents'] / 100:.2f}"
        )

        holdings = portfolio["holdings"]

        if not holdings:
            print("You do not own any shares.")
            return

        for symbol, position in holdings.items():
            print(
                f"{symbol}: {position['shares']} shares, "
                f"paid "
                f"${position['total_paid_cents'] / 100:.2f}"
            )

    def run(self):
        while True:
            try:
                if self.session_token is None:

                    print("\n=== STOCK MARKET EXCHANGE ===")
                    print("1. Register")
                    print("2. Login")
                    print("3. Exit")

                    choice = input("Choose option: ").strip()

                    if choice == "1":
                        self.register()

                    elif choice == "2":
                        self.login()

                    elif choice == "3":
                        print("Goodbye!")
                        break

                    else:
                        print("Choose 1, 2, or 3.")

                else:

                    print(
                        f"\n=== CUSTOMER: {self.username} ==="
                    )

                    print("1. View stock prices")
                    print("2. Search stock")
                    print("3. Buy stock")
                    print("4. Sell stock")
                    print("5. View portfolio")
                    print("6. Check order status")
                    print("7. Cancel pending order")
                    print("8. Logout")
                    print("9. Exit")

                    choice = input("Choose option: ").strip()

                    if choice == "1":
                        self.show_prices()

                    elif choice == "2":
                        self.search_stock()

                    elif choice == "3":
                        self.buy_stock()

                    elif choice == "4":
                        self.sell_stock()

                    elif choice == "5":
                        self.show_portfolio()

                    elif choice == "6":
                        self.check_order_status()

                    elif choice == "7":
                        self.cancel_order()

                    elif choice == "8":
                        self.logout()

                    elif choice == "9":
                        print("Goodbye!")
                        break

                    else:
                        print("Choose a number from 1 to 9.")

            except (
                RuntimeError,
                ValueError,
                KeyError,
                TypeError
            ) as error:
                print(f"Error: {error}")


if __name__ == "__main__":
    CustomerClient().run()
