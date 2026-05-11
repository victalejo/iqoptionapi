"""Asyncio-based IQ Option client (MVP — read-only).

Public API:

    from iqoptionapi.aio import AsyncIQOption

See ``iqoptionapi.aio.client.AsyncIQOption`` for usage.
"""

from iqoptionapi.aio.client import AsyncIQOption
from iqoptionapi.aio.exceptions import (
    AsyncIQOptionError,
    ConnectionError,
    LoginError,
    RequestTimeoutError,
)

__all__ = [
    "AsyncIQOption",
    "AsyncIQOptionError",
    "ConnectionError",
    "LoginError",
    "RequestTimeoutError",
]
