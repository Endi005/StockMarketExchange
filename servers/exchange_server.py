import logging
import secrets
import socketserver
import threading
import traceback
from pathlib import Path

from models.stock import Stock
from services.base_request_handler import BaseRequestHandler
from services.exchange_service import ExchangeService
from services.price_audit_observer import PriceAuditObserver
from repositories.exchange_repository import ExchangeRepository
from services.server_auth import sign_message, verify_message
from services.replay_guard import ReplayGuard
from services.logging_setup import configure_logging
from services.performance_monitor import PerformanceMonitor

from services.correlation_context import (
    get_correlation_id,
    validate_correlation_id
)


BASE_DIR = Path(__file__).resolve().parent.parent
KEY_FILE = BASE_DIR / "data" / "server_key.txt"

logger = logging.getLogger("exchange")

SAFE_ACTIONS = frozenset({
    "get_prices",
    "get_price",
    "get_history",
    "get_statistics"
})


def load_server_key():

    KEY_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if not KEY_FILE.exists():

        KEY_FILE.write_text(
            secrets.token_hex(32),
            encoding="utf-8"
        )

    server_key = KEY_FILE.read_text(
        encoding="utf-8"
    ).strip()

    if not server_key:

        raise RuntimeError(
            "Server authentication credential is empty."
        )

    return server_key


class ExchangeHandler(BaseRequestHandler):

    logger = logger
    safe_actions = SAFE_ACTIONS

    def _validate_request(self, request):

        if not verify_message(
            request,
            self.server.server_key,
            "broker-request"
        ):

            raise ValueError(
                "Invalid server signature."
            )

        if not self.server.replay_guard.accept(
            request.get("nonce"),
            request.get("timestamp")
        ):

            raise ValueError(
                "Duplicate or expired server request."
            )

    def _resolve_correlation_id(self, request):

        # Adopt the incoming correlation ID only after
        # authentication and replay protection succeed.

        if "correlation_id" not in request:

            return get_correlation_id()

        return validate_correlation_id(
            request["correlation_id"]
        )

    def _process_request(self, request):

        action = request.get("action")
        exchange = self.server.exchange

        if action == "get_prices":

            return exchange.get_prices()

        elif action == "get_price":

            return exchange.get_price(
                request.get("symbol")
            )

        elif action == "get_history":

            return exchange.get_history(
                request.get("symbol")
            )

        elif action == "get_statistics":

            statistics = exchange.get_statistics()

            statistics["performance"] = (
                self.server.performance_monitor.get_statistics()
            )

            return statistics

        else:

            raise ValueError(
                "Unknown action. Use get_prices, "
                "get_price, get_history or get_statistics."
            )

    def _handle_error(self, error, action_for_log):

        correlation_id = get_correlation_id()

        # Invalid request encoding.

        if isinstance(error, UnicodeError):

            logger.warning(
                "Exchange request encoding rejected: "
                "correlation_id=%s action=%s error_type=%s",
                correlation_id,
                action_for_log,
                type(error).__name__
            )

            return {
                "ok": False,
                "error_code": "REQUEST_REJECTED",
                "error": (
                    "Invalid request encoding. Send UTF-8 JSON."
                )
            }

        # Expected validation and authentication failures.

        if isinstance(error, ValueError):

            logger.warning(
                "Exchange request rejected: "
                "correlation_id=%s action=%s error_type=%s",
                correlation_id,
                action_for_log,
                type(error).__name__
            )

            return {
                "ok": False,
                "error_code": "REQUEST_REJECTED",
                "error": str(error)
            }

        # Actual connection and timeout failures.

        if isinstance(
            error,
            (ConnectionError, TimeoutError)
        ):

            logger.warning(
                "Exchange communication failure: "
                "correlation_id=%s action=%s error_type=%s",
                correlation_id,
                action_for_log,
                type(error).__name__
            )

            return {
                "ok": False,
                "error_code": "COMMUNICATION_ERROR",
                "error": "Communication failed. Try again."
            }

        # Unexpected internal failures.
        # Log the failure location without exposing
        # exception messages or local variables.

        frames = traceback.extract_tb(
            error.__traceback__
        )

        if frames:

            last_frame = frames[-1]

            location = (
                f"{Path(last_frame.filename).name}:"
                f"{last_frame.lineno}:"
                f"{last_frame.name}"
            )

        else:

            location = "unknown"

        logger.error(
            "Exchange internal failure: "
            "correlation_id=%s action=%s "
            "error_type=%s location=%s",
            correlation_id,
            action_for_log,
            type(error).__name__,
            location
        )

        return {
            "ok": False,
            "error_code": "INTERNAL_ERROR",
            "error": "Internal server error."
        }

    def _prepare_response(self, request, response):

        response["nonce"] = (
            request.get("nonce")
            if isinstance(request, dict)
            else None
        )

        # Use the trusted execution context.

        response["correlation_id"] = (
            get_correlation_id()
        )

        # Authenticate successful and failed responses.

        response["signature"] = sign_message(
            response,
            self.server.server_key,
            "exchange-response"
        )

        return response


class ExchangeServer(socketserver.ThreadingTCPServer):

    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        address,
        exchange,
        server_key
    ):

        self.exchange = exchange
        self.server_key = server_key

        self.replay_guard = ReplayGuard(
            ttl_seconds=300
        )

        self.performance_monitor = PerformanceMonitor()

        super().__init__(
            address,
            ExchangeHandler
        )


def automatic_price_updates(exchange, stop_event):

    while not stop_event.wait(30):

        try:

            prices = exchange.simulate_tick()

            print(
                "Automatic price update:",
                prices
            )

            logger.info(
                "Automatic stock price update completed"
            )

        except (OSError, ValueError) as error:

            logger.error(
                "Automatic price update failed: "
                "error_type=%s",
                type(error).__name__
            )

            print(
                "Price update failed. "
                "Check the Exchange Server log."
            )

        except Exception as error:

            frames = traceback.extract_tb(
                error.__traceback__
            )

            if frames:

                last_frame = frames[-1]

                location = (
                    f"{Path(last_frame.filename).name}:"
                    f"{last_frame.lineno}:"
                    f"{last_frame.name}"
                )

            else:

                location = "unknown"

            logger.error(
                "Unexpected automatic price update failure: "
                "error_type=%s location=%s",
                type(error).__name__,
                location
            )

            print(
                "Unexpected price update failure. "
                "Check the Exchange Server log."
            )


def main():

    configure_logging(
        "exchange",
        BASE_DIR / "data" / "logs"
    )

    logger.info(
        "Exchange Server starting"
    )

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

    exchange.add_observer(PriceAuditObserver())

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

        logger.info(
            "Exchange Server started on port 9001"
        )

        print(
            "Exchange Server running on port 9001"
        )

        print(
            "Automatic price updates enabled!"
        )

        print(
            "Price updates every 30 seconds"
        )

        print(
            "Persistent exchange history enabled!"
        )

        print(
            "Exchange logging enabled!"
        )

        print(
            "Template Method pattern enabled!"
        )

        print(
            "Performance monitoring enabled!"
        )

        print(
            "Cross-server correlation enabled!"
        )

        print(
            "Structured error handling enabled!"
        )

        try:

            server.serve_forever()

        except KeyboardInterrupt:

            print(
                "Stopping Exchange Server..."
            )

        finally:

            logger.info(
                "Exchange Server shutting down"
            )

            stop_event.set()

            update_thread.join(timeout=2)


if __name__ == "__main__":
    main()
