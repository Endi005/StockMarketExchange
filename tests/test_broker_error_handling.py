import unittest

from servers.broker_server import BrokerHandler

from services.application_errors import (
    ExchangeUnavailableError,
    ExchangeProtocolError,
    ExchangeRequestError,
    ServiceUnavailableError
)

from services.correlation_context import (
    correlation_scope
)


class TestBrokerErrorHandling(unittest.TestCase):

    def setUp(self):

        self.handler = object.__new__(BrokerHandler)
        self.correlation_id = "a" * 32

    def handle_error(self, error, action="get_prices"):

        with correlation_scope(self.correlation_id):

            return self.handler._handle_error(
                error,
                action
            )

    def test_exchange_unavailable_error(self):

        response = self.handle_error(
            ExchangeUnavailableError(
                "Internal connection details"
            )
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "EXCHANGE_UNAVAILABLE"
        )

        self.assertNotIn(
            "Internal connection details",
            response["error"]
        )

    def test_exchange_protocol_error(self):

        response = self.handle_error(
            ExchangeProtocolError(
                "Internal signature diagnostic"
            )
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "EXCHANGE_PROTOCOL_ERROR"
        )

        self.assertNotIn(
            "Internal signature diagnostic",
            response["error"]
        )

    def test_exchange_request_error(self):

        response = self.handle_error(
            ExchangeRequestError(
                "Internal exchange rejection details"
            )
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "EXCHANGE_REQUEST_REJECTED"
        )

        self.assertNotIn(
            "Internal exchange rejection details",
            response["error"]
        )

    def test_service_unavailable_error(self):

        response = self.handle_error(
            ServiceUnavailableError(
                "Internal credential file location"
            )
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "SERVICE_UNAVAILABLE"
        )

        self.assertNotIn(
            "Internal credential file location",
            response["error"]
        )

    def test_validation_error_preserves_useful_message(self):

        response = self.handle_error(
            ValueError("Quantity must be positive."),
            "buy"
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "REQUEST_REJECTED"
        )

        self.assertEqual(
            response["error"],
            "Quantity must be positive."
        )

    def test_unexpected_runtime_error_is_hidden(self):

        response = self.handle_error(
            RuntimeError("Sensitive internal information")
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "INTERNAL_ERROR"
        )

        self.assertNotIn(
            "Sensitive internal information",
            response["error"]
        )

    def test_unexpected_type_error_is_hidden(self):

        response = self.handle_error(
            TypeError("Sensitive programming details")
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "INTERNAL_ERROR"
        )

        self.assertNotIn(
            "Sensitive programming details",
            response["error"]
        )

    def test_filesystem_error_is_hidden(self):

        response = self.handle_error(
            OSError("Private database file location")
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "INTERNAL_ERROR"
        )

        self.assertNotIn(
            "Private database file location",
            response["error"]
        )

    def test_connection_error(self):

        response = self.handle_error(
            ConnectionError("Internal socket information")
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "COMMUNICATION_ERROR"
        )

        self.assertNotIn(
            "Internal socket information",
            response["error"]
        )

    def test_timeout_error(self):

        response = self.handle_error(
            TimeoutError("Internal timeout information")
        )

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "COMMUNICATION_ERROR"
        )

    def test_invalid_unicode_request(self):

        error = UnicodeDecodeError(
            "utf-8",
            b"\xff",
            0,
            1,
            "invalid start byte"
        )

        response = self.handle_error(error)

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            "REQUEST_REJECTED"
        )

        self.assertEqual(
            response["error"],
            "Invalid request encoding. Send UTF-8 JSON."
        )

    def test_application_failure_logs_correlation_id(self):

        with self.assertLogs(
            "broker",
            level="WARNING"
        ) as captured:

            self.handle_error(
                ExchangeUnavailableError(
                    "Private diagnostic information"
                )
            )

        output = "\n".join(captured.output)

        self.assertIn(
            "correlation_id=" + self.correlation_id,
            output
        )

        self.assertIn(
            "error_code=EXCHANGE_UNAVAILABLE",
            output
        )

        self.assertIn(
            "action=get_prices",
            output
        )

        self.assertNotIn(
            "Private diagnostic information",
            output
        )

    def test_internal_failure_logs_safe_location(self):

        with self.assertLogs(
            "broker",
            level="ERROR"
        ) as captured:

            try:

                raise RuntimeError(
                    "Secret internal diagnostic"
                )

            except RuntimeError as error:

                response = self.handle_error(error)

        output = "\n".join(captured.output)

        self.assertEqual(
            response["error_code"],
            "INTERNAL_ERROR"
        )

        self.assertIn(
            "correlation_id=" + self.correlation_id,
            output
        )

        self.assertIn(
            "error_type=RuntimeError",
            output
        )

        self.assertIn(
            "test_broker_error_handling.py",
            output
        )

        self.assertIn(
            "test_internal_failure_logs_safe_location",
            output
        )

        self.assertNotIn(
            "Secret internal diagnostic",
            output
        )

    def test_failed_login_does_not_log_password(self):

        password = "PrivatePassword123!"

        with self.assertLogs(
            "broker",
            level="WARNING"
        ) as captured:

            response = self.handle_error(
                ValueError("Invalid username or password."),
                "login"
            )

        output = "\n".join(captured.output)

        self.assertFalse(response["ok"])

        self.assertIn(
            "action=login",
            output
        )

        self.assertIn(
            "correlation_id=" + self.correlation_id,
            output
        )

        self.assertNotIn(password, output)
        self.assertNotIn(password, response["error"])


if __name__ == "__main__":
    unittest.main()