
import json
import hmac
import secrets
import socketserver
import threading
from pathlib import Path

from models.stock import Stock
from services.exchange_service import ExchangeService
from repositories.exchange_repository import ExchangeRepository


BASE_DIR = Path(__file__).resolve().parent.parent
KEY_FILE = BASE_DIR / "data" / "server_key.txt"


def load_server_key():
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not KEY_FILE.exists():
        KEY_FILE.write_text(
            secrets.token_hex(32),
            encoding="utf-8"
        )

    return KEY_FILE.read_text(
        encoding="utf-8"
    ).strip()


class ExchangeHandler(socketserver.StreamRequestHandler):

    def handle(self):
        self.request.settimeout(5)

        try:
            raw = self.rfile.readline(8192)

            if not raw.endswith(b"\n"):
                raise ValueError(
                    "Incomplete request. Send one JSON line."
                )

            request = json.loads(raw.decode("utf-8"))

            if not isinstance(request, dict):
                raise ValueError("Request must be a JSON object.")

            key = request.get("key")

            if not isinstance(key, str) or not hmac.compare_digest(
                key, self.server.server_key
            ):
                raise ValueError(
                    "Authentication refused. "
                    "Use the correct server credential."
                )

            action = request.get("action")
            exchange = self.server.exchange

            if action == "get_prices":
                result = exchange.get_prices()

            elif action == "get_price":
                result = exchange.get_price(
                    request.get("symbol")
                )

            elif action == "get_history":
                result = exchange.get_history(
                    request.get("symbol")
                )

            else:
                raise ValueError(
                    "Unknown action. Use get_prices, "
                    "get_price or get_history."
                )

            response = {"ok": True, "data": result}

        except (ValueError, TypeError, UnicodeError) as error:
            response = {"ok": False, "error": str(error)}

        except OSError:
            response = {
                "ok": False,
                "error": "Communication failed. Try again."
            }

        except Exception:
            response = {
                "ok": False,
                "error": "Internal server error."
            }

        try:
            self.wfile.write(
                (json.dumps(response) + "\n").encode("utf-8")
            )
        except OSError:
            pass


class ExchangeServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, exchange, server_key):
        self.exchange = exchange
        self.server_key = server_key
        super().__init__(address, ExchangeHandler)


def automatic_price_updates(exchange, stop_event):
    while not stop_event.wait(30):
        try:
            prices = exchange.simulate_tick()
            print("Automatic price update:", prices)

        except (OSError, ValueError) as error:
            print("Price update failed:", error)


def main():
    stocks = [
        Stock("Apple", "AAPL", 20000),
        Stock("Tesla", "TSLA", 25000),
        Stock("Microsoft", "MSFT", 40000)
    ]

    repository = ExchangeRepository(
        BASE_DIR / "data" / "exchange.json"
    )

    exchange = ExchangeService(
        stocks,
        repository=repository
    )

    server_key = load_server_key()
    stop_event = threading.Event()

    with ExchangeServer(
        ("127.0.0.1", 9001),
        exchange,
        server_key
    ) as server:

        update_thread = threading.Thread(
            target=automatic_price_updates,
            args=(exchange, stop_event),
            daemon=True
        )

        update_thread.start()

        print("Exchange Server running on port 9001")
        print("Automatic price updates enabled!")
        print("Price updates every 30 seconds")
        print("Persistent exchange history enabled!")

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Stopping Exchange Server...")
        finally:
            stop_event.set()
            update_thread.join(timeout=2)


if __name__ == "__main__":
    main()
