
import json
import os
import socketserver
from pathlib import Path

from services.exchange_gateway import ExchangeGateway
from services.customer_service import CustomerService
from services.admin_otp_service import AdminOTPService
from services.admin_auth_service import AdminAuthService
from repositories.customer_repository import CustomerRepository


BASE_DIR = Path(__file__).resolve().parent.parent


class BrokerHandler(socketserver.StreamRequestHandler):

    def handle(self):
        self.request.settimeout(5)

        try:
            raw = self.rfile.readline(8192)

            if not raw.endswith(b"\n"):
                raise ValueError(
                    "Incomplete request. Send one complete JSON line."
                )

            request = json.loads(raw.decode("utf-8"))

            if not isinstance(request, dict):
                raise ValueError("Request must be a JSON object.")

            result = self._process_request(request)

            response = {"ok": True, "data": result}

        except (ValueError, TypeError, RuntimeError) as error:
            response = {"ok": False, "error": str(error)}

        except (OSError, UnicodeError):
            response = {
                "ok": False,
                "error": "Communication failed. Try again."
            }

        except Exception:
            response = {
                "ok": False,
                "error": "Internal server error. Contact administrator."
            }

        try:
            self.wfile.write(
                (json.dumps(response) + "\n").encode("utf-8")
            )
        except OSError:
            pass

    def _process_request(self, request):
        action = request.get("action")

        customer_service = self.server.customer_service
        admin_auth = self.server.admin_auth

        # Administrator operations
        if action == "admin_request_otp":
            return admin_auth.request_otp(
                request.get("admin_password")
            )

        if action == "admin_login":
            return admin_auth.login(
                request.get("otp")
            )

        
        if action in (
            "admin_status",
            "admin_logout",
            "admin_statistics",
            "admin_exchange_statistics"
        ):
            admin_token = request.get("admin_token")
            admin_auth.require_admin(admin_token)

            if action == "admin_logout":
                return admin_auth.logout(admin_token)

            if action == "admin_statistics":
                return customer_service.get_statistics()

            if action == "admin_exchange_statistics":
                return self.server.gateway.get_statistics()

            return {
                "server": "Broker Server",
                "administrator_authenticated": True
            }

        # Customer registration and login
        if action == "register":
            return customer_service.register(
                request.get("username"),
                request.get("password")
            )

        if action == "login":
            token = customer_service.login(
                request.get("username"),
                request.get("password")
            )

            return {"session_token": token}

        # Remaining customer operations require login
        token = request.get("session_token")
        customer_service.get_username(token)

        if action == "logout":
            return customer_service.logout(token)

        elif action == "get_prices":
            return self.server.gateway.get_prices()

        elif action == "get_price":
            return self.server.gateway.get_price(
                request.get("symbol")
            )

        elif action == "get_portfolio":
            return customer_service.get_portfolio(token)

        elif action == "buy":
            return customer_service.buy_stock(
                token,
                request.get("symbol"),
                request.get("quantity")
            )

        elif action == "sell":
            return customer_service.sell_stock(
                token,
                request.get("symbol"),
                request.get("quantity")
            )

        else:
            raise ValueError(
                "Unknown action. Choose a valid operation."
            )


class BrokerServer(socketserver.ThreadingTCPServer):

    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        address,
        customer_service,
        gateway,
        admin_auth
    ):
        self.customer_service = customer_service
        self.gateway = gateway
        self.admin_auth = admin_auth

        super().__init__(address, BrokerHandler)


def main():
    gateway = ExchangeGateway()

    customer_repository = CustomerRepository(
        BASE_DIR / "data" / "customers.json"
    )

    customer_service = CustomerService(
        customer_repository,
        gateway
    )

    admin_password = os.environ.get("STOCK_ADMIN_PASSWORD")

    if not admin_password:
        raise RuntimeError(
            "Set STOCK_ADMIN_PASSWORD before starting the broker."
        )

    otp_service = AdminOTPService(
        BASE_DIR / "data" / "admin_broker_mailbox.txt"
    )

    admin_auth = AdminAuthService(
        otp_service,
        admin_password
    )

    with BrokerServer(
        ("127.0.0.1", 9002),
        customer_service,
        gateway,
        admin_auth
    ) as server:

        print("Broker Server running on port 9002")
        print("Individual customer accounts enabled!")
        print("Trading and persistent storage enabled!")
        print("Administrator OTP authentication enabled!")

        server.serve_forever()


if __name__ == "__main__":
    main()

