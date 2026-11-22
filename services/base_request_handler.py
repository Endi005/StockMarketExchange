
import json
import socketserver


class BaseRequestHandler(socketserver.StreamRequestHandler):

  
    def handle(self):
        request = {}
        action_for_log = "unknown"

        try:
            request = self._read_request()

            action = request.get("action")
            if isinstance(action, str) and action in self.safe_actions:
                action_for_log = action

            self._validate_request(request)
            result = self._process_request(request)

            self.logger.info(
                "Request completed: action=%s",
                action_for_log
            )

            response = {
                "ok": True,
                "data": result
            }

        except Exception as error:
            response = self._handle_error(error, action_for_log)

        response = self._prepare_response(request, response)

        try:
            self.wfile.write(
                (json.dumps(response) + "\n").encode("utf-8")
            )
        except OSError:
            self.logger.warning("Failed to send server response")


    def _read_request(self):
        self.request.settimeout(5)

        raw = self.rfile.readline(8192)

        if not raw.endswith(b"\n"):
            raise ValueError(
                "Incomplete request. Send one complete JSON line."
            )

        request = json.loads(raw.decode("utf-8"))

        if not isinstance(request, dict):
            raise ValueError("Request must be a JSON object.")

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
