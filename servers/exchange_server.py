
import json
import hmac
import secrets
import socketserver
from pathlib import Path

from models.stock import Stock
from services.exchange_service import ExchangeService


BASE_DIR = Path(__file__).resolve().parent.parent
KEY_FILE = BASE_DIR / "data" / "server_key.txt"


def load_server_key():
    KEY_FILE.parent.mkdir(exist_ok=True)

    if not KEY_FILE.exists():
        KEY_FILE.write_text(
            secrets.token_hex(32), encoding="utf-8"
        )

    return KEY_FILE.read_text(encoding="utf-8").strip()


class ExchangeHandler(socketserver.StreamRequestHandler):

    def handle(self):
        try:
            raw = self.rfile.readline(8192)
            request = json.loads(raw.decode("utf-8"))

            if not isinstance(request, dict):
                raise ValueError("Request must be a JSON object.")

            key = request.get("key")

            if not isinstance(key, str) or not hmac.compare_digest(
                key, self.server.server_key
            ):
                raise ValueError(
                    "Authentication refused. Use the broker server credential."
                )

            action = request.get("action")

            if action == "get_prices":
                result = self.server.exchange.get_prices()

            elif action == "get_price":
                result = self.server.exchange.get_price(
                    request.get("symbol")
                )

            elif action == "get_history":
                result = self.server.exchange.get_history(
                    request.get("symbol")
                )

            else:
                raise ValueError(
                    "Unknown action. Use get_prices, get_price or get_history."
                )

            response = {"ok": True, "data": result}

        except (ValueError, UnicodeError) as error:
            response = {"ok": False, "error": str(error)}

        except Exception:
            response = {
                "ok": False,
                "error": "Internal server error. Contact the administrator."
            }

        self.wfile.write(
            (json.dumps(response) + "\n").encode("utf-8")
        )


class ExchangeServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, exchange, server_key):
        self.exchange = exchange
        self.server_key = server_key
        super().__init__(address, ExchangeHandler)


def main():
    stocks = [
        Stock("Apple", "AAPL", 20000),
        Stock("Tesla", "TSLA", 25000),
        Stock("Microsoft", "MSFT", 40000)
    ]

    exchange = ExchangeService(stocks)
    server_key = load_server_key()

    with ExchangeServer(
        ("127.0.0.1", 9001), exchange, server_key
    ) as server:
        print("Exchange Server running on port 9001")
        print("Waiting for broker requests...")
        server.serve_forever()


if __name__ == "__main__":
    main()
