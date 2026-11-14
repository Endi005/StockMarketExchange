
import json
import socket
import secrets
import time
from pathlib import Path

from services.server_auth import sign_message, verify_message


class ExchangeGateway:

    def __init__(self, host="127.0.0.1", port=9001):
        self.host = host
        self.port = port

        base_dir = Path(__file__).resolve().parent.parent
        self.key_file = base_dir / "data" / "server_key.txt"

    def send_request(self, action, symbol=None):
        if not self.key_file.exists():
            raise RuntimeError(
                "Server credential missing. Start the exchange first."
            )

        server_key = self.key_file.read_text(
            encoding="utf-8"
        ).strip()

        nonce = secrets.token_urlsafe(24)

        request = {
            "action": action,
            "nonce": nonce,
            "timestamp": time.time()
        }

        if symbol is not None:
            request["symbol"] = symbol

        request["signature"] = sign_message(
            request,
            server_key,
            "broker-request"
        )

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
                "Exchange unavailable. Check that its server is running."
            ) from error

        if not response_line or not response_line.endswith(b"\n"):
            raise RuntimeError("Invalid response from exchange.")

        try:
            response = json.loads(response_line)
        except (ValueError, UnicodeError) as error:
            raise RuntimeError(
                "Exchange returned invalid JSON."
            ) from error

        if not isinstance(response, dict):
            raise RuntimeError("Invalid exchange response format.")

        if not verify_message(
            response,
            server_key,
            "exchange-response"
        ):
            raise RuntimeError(
                "Exchange response authentication failed."
            )

        if response.get("nonce") != nonce:
            raise RuntimeError(
                "Exchange response nonce mismatch."
            )

        if response.get("ok") is not True:
            raise RuntimeError(
                response.get("error", "Exchange request failed.")
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

