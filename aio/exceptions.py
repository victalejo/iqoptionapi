"""Exception hierarchy for the async client."""

from __future__ import annotations


class AsyncIQOptionError(Exception):
    """Base error for the async client."""


class LoginError(AsyncIQOptionError):
    """Raised when authentication fails (HTTP login or WS authenticate)."""


class ConnectionError(AsyncIQOptionError):  # noqa: A001 - shadowing builtin is intentional inside this namespace
    """Raised when the WebSocket cannot be established or drops."""


class RequestTimeoutError(AsyncIQOptionError):
    """Raised when a request_id-correlated response is not received in time."""
