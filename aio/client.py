"""High-level async client facade for IQ Option (read-only MVP)."""

from __future__ import annotations

import asyncio
import contextlib
import itertools
from typing import Any, AsyncIterator

import iqoptionapi.constants as op_codes
from iqoptionapi.aio.exceptions import AsyncIQOptionError
from iqoptionapi.aio.http import async_login
from iqoptionapi.aio.ws import AsyncWebSocketClient, DEFAULT_WSS_URL


def _resolve_active_id(active: str | int) -> int:
    """Translate a string active name (e.g. 'EURUSD') to its numeric id.

    Accepts an int unchanged. Raises ``KeyError`` if the name is unknown.
    """
    if isinstance(active, int):
        return active
    try:
        return int(op_codes.ACTIVES[active])
    except KeyError as exc:
        raise KeyError(f"Unknown active name {active!r}") from exc


class AsyncIQOption:
    """Asyncio-based IQ Option client (read-only MVP).

    Usage::

        async with AsyncIQOption(email, password) as client:
            balance = await client.get_balance()
            candles = await client.get_candles("EURUSD", 60, 50, endtime)

    All trading methods are intentionally absent in this release; this
    client is for connection, profile/balance lookup, and market data
    only.
    """

    def __init__(
        self,
        email: str,
        password: str,
        *,
        wss_url: str = DEFAULT_WSS_URL,
        login_url: str | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._wss_url = wss_url
        self._login_url = login_url
        self._ws: AsyncWebSocketClient | None = None
        self._request_id_counter = itertools.count(1)

    # ----- lifecycle --------------------------------------------------------

    async def connect(self) -> None:
        if self._ws is not None:
            return  # already connected
        if self._login_url is not None:
            ssid = await async_login(
                self._email, self._password, login_url=self._login_url
            )
        else:
            ssid = await async_login(self._email, self._password)
        ws = AsyncWebSocketClient(ssid, wss_url=self._wss_url)
        await ws.connect()
        self._ws = ws

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def __aenter__(self) -> "AsyncIQOption":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    # ----- account ---------------------------------------------------------

    async def get_profile(self) -> dict[str, Any]:
        ws = self._require_connected()
        return await ws.wait_for_profile()

    async def get_balances(self) -> list[dict[str, Any]]:
        ws = self._require_connected()
        return await ws.wait_for_balances()

    async def get_balance(self) -> dict[str, Any]:
        """Return the currently-active balance (practice if type==4).

        IQ Option exposes multiple balances per account; this picks the
        practice balance if present, otherwise the first one returned.
        """
        balances = await self.get_balances()
        if not balances:
            raise AsyncIQOptionError("Server returned no balances")
        for b in balances:
            if b.get("type") == 4:  # practice
                return b
        return balances[0]

    # ----- market data -----------------------------------------------------

    async def get_candles(
        self,
        active: str | int,
        size: int,
        count: int,
        endtime: int,
        *,
        timeout: float = 10.0,
    ) -> list[dict[str, Any]]:
        """Fetch up to ``count`` candles of ``size`` seconds, ending at
        ``endtime`` (unix seconds), for ``active`` (e.g. 'EURUSD').
        """
        ws = self._require_connected()
        active_id = _resolve_active_id(active)
        req_id = self._next_request_id()
        body = {
            "name": "get-candles",
            "version": "2.0",
            "body": {
                "active_id": active_id,
                "size": size,
                "to": int(endtime),
                "count": int(count),
            },
        }
        response = await ws.send_and_wait(
            "sendMessage", body, request_id=req_id, timeout=timeout
        )
        msg = response.get("msg") or {}
        return list(msg.get("candles") or [])

    async def stream_candles(
        self,
        active: str | int,
        size: int,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async iterator yielding ``candle-generated`` payloads.

        Sends ``subscribeMessage`` on entry and ``unsubscribeMessage`` on
        cleanup (whether the iterator is exhausted, broken from, or the
        surrounding task is cancelled).
        """
        ws = self._require_connected()
        active_id = _resolve_active_id(active)
        queue = ws.subscribe_candles(active_id, size)

        subscribe_msg = {
            "name": "candle-generated",
            "params": {
                "routingFilters": {"active_id": active_id, "size": size},
            },
        }
        unsubscribe_msg = {
            "name": "candle-generated",
            "params": {
                "routingFilters": {"active_id": active_id, "size": size},
            },
        }

        await ws.send("subscribeMessage", subscribe_msg)
        try:
            while True:
                yield await queue.get()
        finally:
            with contextlib.suppress(Exception):
                await ws.send("unsubscribeMessage", unsubscribe_msg)
            ws.unsubscribe_candles(active_id, size)

    # ----- internals -------------------------------------------------------

    def _next_request_id(self) -> str:
        return str(next(self._request_id_counter))

    def _require_connected(self) -> AsyncWebSocketClient:
        if self._ws is None:
            raise AsyncIQOptionError(
                "Not connected: call connect() or use 'async with'"
            )
        return self._ws
