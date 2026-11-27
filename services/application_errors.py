class ApplicationError(RuntimeError):
    """Base exception for controlled operational failures."""

    error_code = "REQUEST_FAILED"
    public_message = "The operation could not be completed."


class ExchangeUnavailableError(ApplicationError):
    """The exchange server cannot currently be reached."""

    error_code = "EXCHANGE_UNAVAILABLE"
    public_message = (
        "Exchange unavailable. Please try again later."
    )


class ExchangeProtocolError(ApplicationError):
    """The exchange returned an invalid or untrusted response."""

    error_code = "EXCHANGE_PROTOCOL_ERROR"
    public_message = (
        "Exchange communication failed. Please try again later."
    )


class ExchangeRequestError(ApplicationError):
    """The exchange rejected an authenticated request."""

    error_code = "EXCHANGE_REQUEST_REJECTED"
    public_message = (
        "The exchange rejected the request. "
        "Check your request and try again."
    )


class ServiceUnavailableError(ApplicationError):
    """A required internal service is unavailable."""

    error_code = "SERVICE_UNAVAILABLE"
    public_message = (
        "The service is temporarily unavailable. "
        "Please try again later."
    )