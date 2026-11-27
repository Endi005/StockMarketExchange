import unittest

from services.application_errors import (
    ApplicationError,
    ExchangeUnavailableError,
    ExchangeProtocolError,
    ExchangeRequestError,
    ServiceUnavailableError
)


class TestApplicationErrors(unittest.TestCase):

    def test_application_error_inherits_runtime_error(self):

        error = ApplicationError("Internal diagnostic")

        self.assertIsInstance(error, RuntimeError)

    def test_exchange_unavailable_error(self):

        error = ExchangeUnavailableError()

        self.assertEqual(
            error.error_code,
            "EXCHANGE_UNAVAILABLE"
        )

    def test_exchange_protocol_error(self):

        error = ExchangeProtocolError()

        self.assertEqual(
            error.error_code,
            "EXCHANGE_PROTOCOL_ERROR"
        )

    def test_exchange_request_error(self):

        error = ExchangeRequestError()

        self.assertEqual(
            error.error_code,
            "EXCHANGE_REQUEST_REJECTED"
        )

    def test_service_unavailable_error(self):

        error = ServiceUnavailableError()

        self.assertEqual(
            error.error_code,
            "SERVICE_UNAVAILABLE"
        )

    def test_public_message_does_not_expose_internal_details(self):

        error = ExchangeProtocolError(
            "Internal authentication diagnostic"
        )

        self.assertNotIn(
            "Internal authentication diagnostic",
            error.public_message
        )

        self.assertEqual(
            str(error),
            "Internal authentication diagnostic"
        )


if __name__ == "__main__":
    unittest.main()