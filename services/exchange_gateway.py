import json
import socket
import secrets
import time
from pathlib import Path

from services.server_auth import sign_message, verify_message

from services.correlation_context import (
    get_correlation_id,
    generate_correlation_id
)

from services.application_errors import (
    ExchangeUnavailableError,
    ExchangeProtocolError,
    ExchangeRequestError,
    ServiceUnavailableError
)


class ExchangeGateway:

    def __init__(self, host="127.0.0.1", port=9001):
        self.host = host
        self.port = port

        base_dir = Path(__file__).resolve().parent.parent
        self.key_file = base_dir / "data" / "server_key.txt"

    def send_request(self, action, symbol=None):

        # Load the server authentication credential.

        if not self.key_file.exists():
            raise ServiceUnavailableError(
                "Server credential missing. Start the exchange first."
            )

        try:
            server_key = self.key_file.read_text(
                encoding="utf-8"
            ).strip()

        except (OSError, UnicodeError) as error:

            raise ServiceUnavailableError(
                "Server credential could not be loaded."
            ) from error

        if not server_key:
            raise ServiceUnavailableError(
                "Server credential is empty."
            )

        # Create request authentication and correlation data.

        nonce = secrets.token_urlsafe(24)

        correlation_id = get_correlation_id()

        if correlation_id is None:
            correlation_id = generate_correlation_id()

        request = {
            "action": action,
            "nonce": nonce,
            "timestamp": time.time(),
            "correlation_id": correlation_id
        }

        if symbol is not None:
            request["symbol"] = symbol

        request["signature"] = sign_message(
            request,
            server_key,
            "broker-request"
        )

        # Communicate with the Exchange Server.

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

            raise ExchangeUnavailableError(
                "Exchange unavailable. Check that its server is running."
            ) from error

        # Validate the response format.

        if not response_line or not response_line.endswith(b"\n"):
            raise ExchangeProtocolError(
                "Invalid response from exchange."
            )

        try:
            response = json.loads(response_line)

        except (ValueError, UnicodeError) as error:

            raise ExchangeProtocolError(
                "Exchange returned invalid JSON."
            ) from error

        if not isinstance(response, dict):
            raise ExchangeProtocolError(
                "Invalid exchange response format."
            )

        # Authenticate the Exchange Server response.

        if not verify_message(
            response,
            server_key,
            "exchange-response"
        ):
            raise ExchangeProtocolError(
                "Exchange response authentication failed."
            )

        if response.get("nonce") != nonce:
            raise ExchangeProtocolError(
                "Exchange response nonce mismatch."
            )

        # Authenticated error responses may contain a
        # locally generated exchange correlation ID.

        if response.get("ok") is False:

            error_message = response.get("error")

            if not isinstance(error_message, str):
                error_message = "Exchange request failed."

            raise ExchangeRequestError(error_message)

        if response.get("ok") is not True:
            raise ExchangeProtocolError(
                "Invalid exchange response status."
            )

        # Successful responses must belong to the
        # same operation as the outgoing request.

        if response.get("correlation_id") != correlation_id:
            raise ExchangeProtocolError(
                "Exchange response correlation ID mismatch."
            )

        if "data" not in response:
            raise ExchangeProtocolError(
                "Exchange response data is missing."
            )

        return response["data"]

    def get_prices(self):
        return self.send_request("get_prices")

    def get_price(self, symbol):
        return self.send_request("get_price", symbol)

    def get_history(self, symbol):
        return self.send_request("get_history", symbol)

    def get_statistics(self):
        return self.send_request("get_statistics")