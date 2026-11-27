import json
import re
import socket
import unittest

from unittest.mock import patch

from tests import test_server_integration


class TestErrorIntegration(unittest.TestCase):

    # Reuse the existing integration test environment
    # without duplicating its existing test cases.

    setUp = test_server_integration.ServerIntegrationTests.setUp

    send_broker_request = (
        test_server_integration.ServerIntegrationTests
        .send_broker_request
    )

    register_and_login = (
        test_server_integration.ServerIntegrationTests
        .register_and_login
    )

    finish_exchange_requests = (
        test_server_integration.ServerIntegrationTests
        .finish_exchange_requests
    )

    def assert_safe_error(self, response, expected_code):

        self.assertFalse(response["ok"])

        self.assertEqual(
            response["error_code"],
            expected_code
        )

        self.assertNotIn("data", response)

        self.assertIsInstance(
            response["error"],
            str
        )

    def test_exchange_unavailable_returns_structured_error(self):

        token = self.register_and_login(
            "UnavailableExchangeUser"
        )

        # Stop the real Exchange Server.

        self.finish_exchange_requests()

        response = self.send_broker_request({
            "action": "get_prices",
            "session_token": token
        })

        self.assert_safe_error(
            response,
            "EXCHANGE_UNAVAILABLE"
        )

        self.assertEqual(
            response["error"],
            "Exchange unavailable. Please try again later."
        )

    def test_exchange_authentication_failure(self):

        token = self.register_and_login(
            "AuthenticationFailureUser"
        )

        # Give the Broker an incorrect server credential.

        wrong_key = "incorrect-server-secret"

        self.gateway.key_file.write_text(
            wrong_key,
            encoding="utf-8"
        )

        response = self.send_broker_request({
            "action": "get_prices",
            "session_token": token
        })

        self.assert_safe_error(
            response,
            "EXCHANGE_PROTOCOL_ERROR"
        )

        self.assertNotIn(
            wrong_key,
            json.dumps(response)
        )

    def test_unexpected_broker_failure_is_hidden(self):

        token = self.register_and_login(
            "InternalFailureUser"
        )

        secret = "Sensitive internal database information"

        with patch.object(
            self.gateway,
            "get_prices",
            side_effect=RuntimeError(secret)
        ):

            with self.assertLogs(
                "broker",
                level="ERROR"
            ) as captured:

                response = self.send_broker_request({
                    "action": "get_prices",
                    "session_token": token
                })

        self.assert_safe_error(
            response,
            "INTERNAL_ERROR"
        )

        self.assertNotIn(
            secret,
            json.dumps(response)
        )

        self.assertNotIn(
            secret,
            "\n".join(captured.output)
        )

    def test_customer_password_is_not_logged(self):

        self.register_and_login(
            "PasswordSecurityUser"
        )

        wrong_password = "PrivateWrongPassword123!"

        with self.assertLogs(
            "broker",
            level="INFO"
        ) as captured:

            response = self.send_broker_request({
                "action": "login",
                "username": "PasswordSecurityUser",
                "password": wrong_password
            })

        self.assert_safe_error(
            response,
            "REQUEST_REJECTED"
        )

        output = "\n".join(captured.output)

        self.assertIn("action=login", output)

        self.assertNotIn(
            wrong_password,
            output
        )

        self.assertNotIn(
            wrong_password,
            json.dumps(response)
        )

    def test_admin_password_is_not_logged(self):

        wrong_password = "PrivateAdminPassword456!"

        with self.assertLogs(
            "broker",
            level="INFO"
        ) as captured:

            response = self.send_broker_request({
                "action": "admin_request_otp",
                "admin_password": wrong_password
            })

        self.assert_safe_error(
            response,
            "REQUEST_REJECTED"
        )

        output = "\n".join(captured.output)

        self.assertIn(
            "action=admin_request_otp",
            output
        )

        self.assertNotIn(
            wrong_password,
            output
        )

        self.assertNotIn(
            self.admin_password,
            output
        )

        self.assertNotIn(
            wrong_password,
            json.dumps(response)
        )

        self.assertFalse(
            self.mailbox_path.exists()
        )

    def test_invalid_otp_is_not_logged(self):

        otp_response = self.send_broker_request({
            "action": "admin_request_otp",
            "admin_password": self.admin_password
        })

        self.assertTrue(
            otp_response["ok"],
            otp_response
        )

        actual_otp = (
            self.mailbox_path
            .read_text(encoding="utf-8")
            .strip()
            .rsplit(" ", 1)[-1]
        )

        # Use a unique invalid OTP value so that the
        # confidentiality assertion is deterministic.

        wrong_otp = "PRIVATE_INVALID_OTP_TEST"

        with self.assertLogs(
            "broker",
            level="INFO"
        ) as captured:

            response = self.send_broker_request({
                "action": "admin_login",
                "otp": wrong_otp
            })

        self.assert_safe_error(
            response,
            "REQUEST_REJECTED"
        )

        output = "\n".join(captured.output)

        self.assertIn(
            "action=admin_login",
            output
        )

        self.assertNotIn(
            wrong_otp,
            output
        )

        self.assertNotIn(
            wrong_otp,
            json.dumps(response)
        )

        # A single failed attempt must not invalidate
        # the legitimate OTP.

        valid_response = self.send_broker_request({
            "action": "admin_login",
            "otp": actual_otp
        })

        self.assertTrue(
            valid_response["ok"],
            valid_response
        )

    def test_malformed_request_is_rejected(self):

        with socket.create_connection(
            self.broker_server.server_address,
            timeout=5
        ) as connection:

            connection.settimeout(5)

            with connection.makefile("rwb") as stream:

                # Deliberately send invalid JSON.

                stream.write(b'{"action": invalid}\n')
                stream.flush()

                response = json.loads(
                    stream.readline(8192)
                )

                self.assertEqual(
                    stream.read(),
                    b""
                )

        self.assert_safe_error(
            response,
            "REQUEST_REJECTED"
        )

        # Confirm that the server still works.

        token = self.register_and_login(
            "AfterMalformedRequestUser"
        )

        valid_response = self.send_broker_request({
            "action": "get_prices",
            "session_token": token
        })

        self.assertTrue(
            valid_response["ok"],
            valid_response
        )

    def test_failed_cross_server_request_is_traceable(self):

        token = self.register_and_login(
            "FailedCorrelationUser"
        )

        secret = "Private exchange implementation failure"

        with patch.object(
            self.exchange_server.exchange,
            "get_prices",
            side_effect=RuntimeError(secret)
        ):

            with self.assertLogs(
                "broker",
                level="INFO"
            ) as broker_logs:

                with self.assertLogs(
                    "exchange",
                    level="INFO"
                ) as exchange_logs:

                    response = self.send_broker_request({
                        "action": "get_prices",
                        "session_token": token
                    })

                    self.finish_exchange_requests()

        self.assert_safe_error(
            response,
            "EXCHANGE_REQUEST_REJECTED"
        )

        pattern = (
            r"correlation_id=([0-9a-f]{32}) "
            r"action=get_prices success=False\b"
        )

        broker_output = "\n".join(
            broker_logs.output
        )

        exchange_output = "\n".join(
            exchange_logs.output
        )

        broker_ids = re.findall(
            pattern,
            broker_output
        )

        exchange_ids = re.findall(
            pattern,
            exchange_output
        )

        self.assertEqual(
            len(broker_ids),
            1
        )

        self.assertEqual(
            broker_ids,
            exchange_ids
        )

        self.assertNotIn(
            secret,
            broker_output
        )

        self.assertNotIn(
            secret,
            exchange_output
        )

        self.assertNotIn(
            secret,
            json.dumps(response)
        )


if __name__ == "__main__":
    unittest.main()