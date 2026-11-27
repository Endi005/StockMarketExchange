import re
import uuid
from contextvars import ContextVar
from contextlib import contextmanager


_correlation_id = ContextVar(
    "correlation_id",
    default=None
)


def generate_correlation_id():
    """Generate a unique correlation identifier."""

    return uuid.uuid4().hex


def validate_correlation_id(correlation_id):
    """Validate the format of a correlation identifier."""

    if not isinstance(correlation_id, str):
        raise ValueError("Invalid correlation ID.")

    if re.fullmatch(r"[0-9a-f]{32}", correlation_id) is None:
        raise ValueError("Invalid correlation ID.")

    return correlation_id


def get_correlation_id():
    """Return the correlation ID of the current context."""

    return _correlation_id.get()


@contextmanager
def correlation_scope(correlation_id=None):
    """Temporarily assign a correlation ID to the current context."""

    if correlation_id is None:
        correlation_id = generate_correlation_id()

    validate_correlation_id(correlation_id)

    token = _correlation_id.set(correlation_id)

    try:
        yield correlation_id

    finally:
        _correlation_id.reset(token)