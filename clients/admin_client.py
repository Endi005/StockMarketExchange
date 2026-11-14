
import json
import socket
from getpass import getpass
from pathlib import Path


class AdminClient:

    def __init__(self):
        self.host = "127.0.0.1"
        self.port = 9002
        self.admin_token = None

    def send_request(self, action, **parameters):
        request = {"action": action}
        request.update(parameters)

        if self.admin_token is not None:
            request["admin_token"] = self.admin_token

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
                "Broker Server unavailable. Check that it is running."
            ) from error

        if not response_line.endswith(b"\n"):
            raise RuntimeError(
                "Incomplete server response. Try again."
            )

        try:
            response = json.loads(response_line)
        except (ValueError, UnicodeError) as error:
            raise RuntimeError(
                "Invalid server response."
            ) from error

        if not isinstance(response, dict):
            raise RuntimeError("Invalid response format.")

        if response.get("ok") is not True:
            raise RuntimeError(
                response.get("error", "Request failed.")
            )

        return response["data"]

    def request_otp(self):
        password = getpass("Administrator password: ")

        result = self.send_request(
            "admin_request_otp",
            admin_password=password
        )

        print(result["message"])

        mailbox = (
            Path(__file__).resolve().parent.parent
            / "data"
            / "admin_broker_mailbox.txt"
        )

        print(f"Open this mailbox file to read your OTP:\n{mailbox}")

    def login(self):
        code = input("Enter the 6-digit OTP: ").strip()

        result = self.send_request(
            "admin_login",
            otp=code
        )

        self.admin_token = result["session_token"]
        print("Administrator login successful!")

    def show_status(self):
        result = self.send_request("admin_status")

        print("\n=== BROKER SERVER STATUS ===")
        print(f"Server: {result['server']}")
        print(
            f"Authenticated: "
            f"{result['administrator_authenticated']}"
        )

    def show_statistics(self):
        result = self.send_request("admin_statistics")

        print("\n=== CUSTOMER STATISTICS ===")
        print(f"Registered customers: {result['customer_count']}")
        print(
            f"Total customer cash: "
            f"${result['total_cash_cents'] / 100:.2f}"
        )
        print(f"Total shares owned: {result['total_shares']}")

    def show_exchange_statistics(self):
        result = self.send_request(
            "admin_exchange_statistics"
        )

        print("\n=== EXCHANGE SERVER STATISTICS ===")
        print(f"Available stocks: {result['stock_count']}")

        print("\nCurrent stock prices:")
        for symbol, price_cents in result["prices"].items():
            print(f"  {symbol}: ${price_cents / 100:.2f}")

        print("\nRecorded price history:")
        for symbol, count in result["history_entries"].items():
            print(f"  {symbol}: {count} entries")

    def logout(self):
        self.send_request("admin_logout")
        self.admin_token = None
        print("Administrator logged out successfully.")

    def run(self):
        while True:
            try:
                if self.admin_token is None:
                    print("\n=== ADMIN LOGIN ===")
                    print("1. Request OTP")
                    print("2. Login with OTP")
                    print("3. Exit")

                    choice = input("Choose option: ").strip()

                    if choice == "1":
                        self.request_otp()

                    elif choice == "2":
                        self.login()

                    elif choice == "3":
                        print("Goodbye!")
                        break

                    else:
                        print("Choose 1, 2, or 3.")

                else:
                    print("\n=== ADMIN MENU ===")
                    print("1. View Broker Server status")
                    print("2. View customer statistics")
                    print("3. View Exchange Server statistics")
                    print("4. Logout")
                    print("5. Exit")

                    choice = input("Choose option: ").strip()

                    if choice == "1":
                        self.show_status()

                    elif choice == "2":
                        self.show_statistics()

                    elif choice == "3":
                        self.show_exchange_statistics()

                    elif choice == "4":
                        self.logout()

                    elif choice == "5":
                        print("Goodbye!")
                        break

                    else:
                        print("Choose 1, 2, 3, 4, or 5.")

            except (RuntimeError, ValueError, KeyError) as error:
                print(f"Error: {error}")


if __name__ == "__main__":
    AdminClient().run()
