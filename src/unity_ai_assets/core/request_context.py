"""Request ID context and validation for X-Request-ID."""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

REQUEST_ID_HEADER: str = "X-Request-ID"
MAX_REQUEST_ID_LENGTH: int = 64
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._\-]+$")

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def generate_request_id() -> str:
    """Create a new opaque request identifier."""
    return str(uuid.uuid4())


def is_valid_request_id(value: str) -> bool:
    """Return True when an incoming request ID is safe to echo."""
    if not value or len(value) > MAX_REQUEST_ID_LENGTH:
        return False
    if any(ord(ch) < 32 for ch in value):
        return False
    return _REQUEST_ID_PATTERN.fullmatch(value) is not None


def resolve_request_id(incoming: str | None) -> str:
    """Accept a valid incoming ID or replace it with a generated one."""
    if incoming is not None and is_valid_request_id(incoming.strip()):
        return incoming.strip()
    return generate_request_id()


def set_request_id(request_id: str) -> None:
    """Bind the request ID for the current context (logging / errors)."""
    _request_id_var.set(request_id)


def get_request_id() -> str | None:
    """Return the request ID for the current context, if any."""
    return _request_id_var.get()
