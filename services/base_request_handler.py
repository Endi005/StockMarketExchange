import json
import socketserver
import time

from services.correlation_context import (
    generate_correlation_id,
    correlation_scope,
    get_correlation_id
)


class BaseRequestHandler(socketserver.StreamRequestHandler):

    def handle(self):

        request_id = generate_correlation_id()

        with correlation_scope(request_id):

            self._handle_request(request_id)

    def _handle_request(self, request_id):

        started_at = time.perf_counter()

        request = {}
        action_for_log = "unknown"
        correlation_id = request_id

        success = False
        error_code = "NONE"

        try:

            try:
                request = self._read_request()

                action = request.get("action")

                if (
                    isinstance(action, str)
                    and action in self.safe_actions
                ):
                    action_for_log = action

                self._validate_request(request)

                correlation_id = self._resolve_correlation_id(
                    request
                )

                with correlation_scope(correlation_id):

                    result = self._process_request(request)

                response = {
                    "ok": True,
                    "data": result
                }

            except Exception as error:

                with correlation_scope(correlation_id):

                    response = self._handle_error(
                        error,
                        action_for_log
                    )

            error_code = response.get(
                "error_code",
                "NONE" if response.get("ok") is True
                else "REQUEST_FAILED"
            )

            with correlation_scope(correlation_id):

                response = self._prepare_response(
                    request,
                    response
                )

            self.wfile.write(
                (json.dumps(response) + "\n").encode("utf-8")
            )

            success = response.get("ok") is True

        except OSError:

            error_code = "COMMUNICATION_ERROR"

            self.logger.warning(
                "Response communication failed: "
                "request_id=%s correlation_id=%s action=%s",
                request_id,
                correlation_id,
                action_for_log
            )

        except Exception as error:

            error_code = "INTERNAL_ERROR"

            self.logger.error(
                "Response preparation failed: "
                "request_id=%s correlation_id=%s "
                "action=%s error_type=%s",
                request_id,
                correlation_id,
                action_for_log,
                type(error).__name__
            )

        finally:

            duration_ms = (
                time.perf_counter() - started_at
            ) * 1000

            monitor = getattr(
                getattr(self, "server", None),
                "performance_monitor",
                None
            )

            if monitor is not None:

                monitor.record(
                    action_for_log,
                    success,
                    duration_ms
                )

            message = (
                "Request completed: "
                "request_id=%s correlation_id=%s "
                "action=%s success=%s "
                "error_code=%s duration_ms=%.3f"
            )

            if success:

                self.logger.info(
                    message,
                    request_id,
                    correlation_id,
                    action_for_log,
                    success,
                    error_code,
                    duration_ms
                )

            else:

                self.logger.warning(
                    message,
                    request_id,
                    correlation_id,
                    action_for_log,
                    success,
                    error_code,
                    duration_ms
                )

    def _read_request(self):

        self.request.settimeout(5)

        raw = self.rfile.readline(8192)

        if not raw.endswith(b"\n"):
            raise ValueError(
                "Incomplete request. Send one complete JSON line."
            )

        request = json.loads(raw.decode("utf-8"))

        if not isinstance(request, dict):
            raise ValueError(
                "Request must be a JSON object."
            )

        return request

    def _validate_request(self, request):
        """Child classes can provide their own security checks."""
        pass

    def _resolve_correlation_id(self, request):
        """Use the locally generated correlation ID by default."""

        return get_correlation_id()

    def _process_request(self, request):
        """Each server must implement its own operations."""

        raise NotImplementedError(
            "Subclasses must implement _process_request()."
        )

    def _handle_error(self, error, action_for_log):
        """Each server defines its own error handling."""

        raise NotImplementedError(
            "Subclasses must implement _handle_error()."
        )

    def _prepare_response(self, request, response):
        """Child classes can customize outgoing responses."""

        return response