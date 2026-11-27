import json
import socketserver
import time
import uuid


class BaseRequestHandler(socketserver.StreamRequestHandler):

    def handle(self):

        started_at = time.perf_counter()

        request = {}
        action_for_log = "unknown"
        request_id = uuid.uuid4().hex

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

                result = self._process_request(request)

                response = {
                    "ok": True,
                    "data": result
                }

            except Exception as error:

                response = self._handle_error(
                    error,
                    action_for_log
                )

            error_code = response.get(
                "error_code",
                "NONE" if response.get("ok") is True
                else "REQUEST_FAILED"
            )

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
                "request_id=%s action=%s",
                request_id,
                action_for_log
            )

        except Exception as error:

            error_code = "INTERNAL_ERROR"

            self.logger.error(
                "Response preparation failed: "
                "request_id=%s action=%s error_type=%s",
                request_id,
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

            log_level = "INFO" if success else "WARNING"

            message = (
                "Request completed: "
                "request_id=%s action=%s success=%s "
                "error_code=%s duration_ms=%.3f"
            )

            if log_level == "INFO":

                self.logger.info(
                    message,
                    request_id,
                    action_for_log,
                    success,
                    error_code,
                    duration_ms
                )

            else:

                self.logger.warning(
                    message,
                    request_id,
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