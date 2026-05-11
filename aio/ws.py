"""Async WebSocket client and dispatcher for IQ Option.

This module owns the wire protocol: opening the WebSocket, sending the
``authenticate`` frame, parsing inbound JSON messages, and routing them to
either ``request_id``-correlated futures (for one-shot calls like
``get-candles``) or per-subscription queues (for streaming feeds like
``candle-generated``).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from iqoptionapi.aio.exceptions import ConnectionError, LoginError

logger = logging.getLogger(__name__)

DEFAULT_WSS_URL = "wss://iqoption.com/echo/websocket"
PROTOCOL_VERSION = 3


SubscriptionKey = tuple[str, int, int]  # (kind, active_id, size) for candles


class AsyncWebSocketClient:
    """Manages the WebSocket connection, dispatch, and lifecycle.

    Not meant to be used directly — ``AsyncIQOption`` owns one of these.
    """

    def __init__(self, ssid: str, *, wss_url: str = DEFAULT_WSS_URL) -> None:
        self._ssid = ssid
        self._wss_url = wss_url
        self._ws: ClientConnection | None = None
        self._receive_task: asyncio.Task[None] | None = None
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._subscriptions: dict[SubscriptionKey, asyncio.Queue[dict[str, Any]]] = {}
        self._profile: dict[str, Any] | None = None
        self._balances: list[dict[str, Any]] | None = None
        self._authenticated_event = asyncio.Event()
        self._authenticated_ok: bool | None = None
        self._closed = False
        self._send_lock = asyncio.Lock()
        # Anyone awaiting the first profile / balances message:
        self._profile_event = asyncio.Event()
        self._balances_event = asyncio.Event()

    async def connect(self, *, auth_timeout: float = 15.0) -> None:
        """Open the socket, authenticate, and start the receive loop."""
        try:
            self._ws = await websockets.connect(self._wss_url)
        except (OSError, websockets.WebSocketException) as exc:
            raise ConnectionError(f"WebSocket connect failed: {exc}") from exc

        self._receive_task = asyncio.create_task(
            self._receive_loop(), name="iqoptionapi-aio-receive"
        )

        await self._send_raw(
            {
                "name": "authenticate",
                "msg": {"ssid": self._ssid, "protocol": PROTOCOL_VERSION},
            }
        )

        try:
            await asyncio.wait_for(self._authenticated_event.wait(), timeout=auth_timeout)
        except asyncio.TimeoutError as exc:
            await self.close()
            raise LoginError("Did not receive authenticated response in time") from exc

        if not self._authenticated_ok:
            await self.close()
            raise LoginError("Server rejected ssid (authenticated=False)")

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        if self._receive_task is not None:
            self._receive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._receive_task

        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.close()

        # Fail any still-pending futures so callers don't hang forever.
        exc = ConnectionError("WebSocket closed")
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()
        self._subscriptions.clear()

    async def send_and_wait(
        self,
        name: str,
        msg: dict[str, Any] | str,
        *,
        request_id: str,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        """Send a frame and await the matching response by ``request_id``.

        The response future is resolved by the receive loop when it sees a
        message carrying the same ``request_id``.
        """
        if request_id in self._pending:
            raise ValueError(f"Duplicate request_id: {request_id}")

        fut: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = fut
        try:
            await self._send_raw({"name": name, "msg": msg, "request_id": request_id})
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError as exc:
            from iqoptionapi.aio.exceptions import RequestTimeoutError

            raise RequestTimeoutError(
                f"No response for request_id={request_id} within {timeout}s"
            ) from exc
        finally:
            self._pending.pop(request_id, None)

    def subscribe_candles(self, active_id: int, size: int) -> asyncio.Queue[dict[str, Any]]:
        """Register a queue for ``candle-generated`` messages of this stream.

        Caller is responsible for actually sending the ``subscribeMessage``
        frame (the client.py layer does that) and for calling
        ``unsubscribe_candles`` when done.
        """
        key: SubscriptionKey = ("candle-generated", active_id, size)
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscriptions[key] = queue
        return queue

    def unsubscribe_candles(self, active_id: int, size: int) -> None:
        self._subscriptions.pop(("candle-generated", active_id, size), None)

    async def send(self, name: str, msg: dict[str, Any], *, request_id: str = "") -> None:
        """Fire-and-forget send (no future, no waiting)."""
        await self._send_raw({"name": name, "msg": msg, "request_id": request_id})

    @property
    def profile(self) -> dict[str, Any] | None:
        return self._profile

    @property
    def balances(self) -> list[dict[str, Any]] | None:
        return self._balances

    async def wait_for_profile(self, timeout: float = 10.0) -> dict[str, Any]:
        await asyncio.wait_for(self._profile_event.wait(), timeout=timeout)
        assert self._profile is not None
        return self._profile

    async def wait_for_balances(self, timeout: float = 10.0) -> list[dict[str, Any]]:
        await asyncio.wait_for(self._balances_event.wait(), timeout=timeout)
        assert self._balances is not None
        return self._balances

    # ----- internals --------------------------------------------------------

    async def _send_raw(self, payload: dict[str, Any]) -> None:
        if self._ws is None:
            raise ConnectionError("Not connected")
        data = json.dumps(payload)
        async with self._send_lock:
            try:
                await self._ws.send(data)
            except websockets.WebSocketException as exc:
                raise ConnectionError(f"Send failed: {exc}") from exc
        logger.debug("ws -> %s", data)

    async def _receive_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("Ignoring non-JSON WS frame: %r", raw[:200])
                    continue
                logger.debug("ws <- %s", message.get("name"))
                self._dispatch(message)
        except websockets.ConnectionClosed:
            logger.info("WebSocket closed by peer")
        except asyncio.CancelledError:
            raise
        # Mark everything as failed if the loop exits abnormally.
        exc = ConnectionError("Receive loop terminated")
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(exc)

    def _dispatch(self, message: dict[str, Any]) -> None:
        name = message.get("name")
        req_id = message.get("request_id") or ""

        # --- authentication ---
        if name == "authenticated":
            self._authenticated_ok = bool(message.get("msg"))
            self._authenticated_event.set()
            return

        # --- heartbeat: echo back ---
        if name == "heartbeat":
            # Echo with the server's timestamp; fire-and-forget.
            asyncio.create_task(
                self._send_raw({"name": "heartbeat", "msg": message.get("msg")})
            )
            return

        # --- one-shot responses keyed by request_id ---
        if req_id and req_id in self._pending:
            fut = self._pending[req_id]
            if not fut.done():
                fut.set_result(message)
            # Don't return — some frames also update state (e.g. profile).

        # --- profile / balances broadcasts ---
        if name == "profile":
            self._profile = message.get("msg") or {}
            self._profile_event.set()
            return
        if name == "balances":
            msg = message.get("msg")
            if isinstance(msg, list):
                self._balances = msg
                self._balances_event.set()
            return

        # --- streaming: candle-generated ---
        if name == "candle-generated":
            payload = message.get("msg") or {}
            active_id = payload.get("active_id")
            size = payload.get("size")
            if isinstance(active_id, int) and isinstance(size, int):
                queue = self._subscriptions.get(("candle-generated", active_id, size))
                if queue is not None:
                    queue.put_nowait(payload)
            return
