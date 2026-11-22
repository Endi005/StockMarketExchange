
import logging
import os
import socketserver
from pathlib import Path

from services.base_request_handler import BaseRequestHandler
from services.exchange_gateway import ExchangeGateway
from services.admin_otp_service import AdminOTPService
from services.admin_auth_service import AdminAuthService
from services.logging_setup import configure_logging

from repositories.trading_repository import TradingRepository
from services.order_processor import OrderProcessor
from services.order_queue import OrderQueue
from services.queued_customer_service import QueuedCustomerService


BASE_DIR = Path(__file__).resolve().parent.parent

logger = logging.getLogger("broker")

SAFE_ACTIONS = frozenset({
    "register",
    "login",
    "logout",
    "get_prices",
    "get_price",
    "get_portfolio",
    "buy",
    "sell",
    "get_order",
    "cancel_order",
    "admin_request_otp",
    "admin_login",
    "admin_status",
    "admin_logout",
    "admin_statistics",
    "admin_exchange_statistics"
})


class BrokerHandler(BaseRequestHandler):

    logger = logger
    safe_actions = SAFE_ACTIONS

    def _handle_error(self, error, action_for_log):

        if isinstance(error, (ValueError, TypeError, RuntimeError)):
            logger.warning(
                "Request rejected: action=%s error_type=%s",
                action_for_log,
                type(error).__name__
            )

            return {
                "ok": False,
                "error_code": "REQUEST_REJECTED",
                "error": str(error)
            }

        if isinstance(error, (OSError, UnicodeError)):
            logger.warning(
                "Communication failure: action=%s error_type=%s",
                action_for_log,
                type(error).__name__
            )

            return {
                "ok": False,
                "error_code": "COMMUNICATION_ERROR",
                "error": "Communication failed. Try again."
            }

        logger.error(
            "Internal failure: action=%s error_type=%s",
            action_for_log,
            type(error).__name__
        )

        return {
            "ok": False,
            "error_code": "INTERNAL_ERROR",
            "error": "Internal server error. Contact administrator."
        }

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

            return {
                "session_token": token
            }

        # Authenticated customer operations

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

        # Persistent stock orders

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

        elif action == "get_order":
            return customer_service.get_order(
                token,
                request.get("order_id")
            )

        elif action == "cancel_order":
            return customer_service.cancel_order(
                token,
                request.get("order_id")
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

    configure_logging(
        "broker",
        BASE_DIR / "data" / "logs"
    )

    logger.info("Broker Server starting")

    # Exchange connection

    gateway = ExchangeGateway()

    # Persistent customer and order database

    trading_repository = TradingRepository(
        BASE_DIR / "data" / "trading.json"
    )

    order_processor = OrderProcessor(
        trading_repository,
        gateway
    )

    # Producer/Consumer queue

    order_queue = OrderQueue(order_processor)

    customer_service = QueuedCustomerService(
        order_queue
    )

    # Administrator authentication

    admin_password = os.environ.get(
        "STOCK_ADMIN_PASSWORD"
    )

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

    # Start Broker Server

    order_queue.start()

    try:
        with BrokerServer(
            ("127.0.0.1", 9002),
            customer_service,
            gateway,
            admin_auth
        ) as server:

            logger.info(
                "Broker Server started on port 9002"
            )

            print("Broker Server running on port 9002")
            print("Customer accounts enabled!")
            print("Persistent order queue enabled!")
            print("Producer/Consumer pattern enabled!")
            print("Stock trading enabled!")
            print("Administrator OTP authentication enabled!")
            print("Broker logging enabled!")
            print("Template Method pattern enabled!")

            server.serve_forever()

    finally:
        logger.info("Broker Server shutting down")
        order_queue.stop()


if __name__ == "__main__":
    main()
