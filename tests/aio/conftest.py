"""Shared pytest fixtures for async-client tests.

Provides an in-process fake IQ Option WebSocket server, exposed as both a
default `fake_server` fixture and a `fake_ws_factory` factory fixture that
lets individual tests configure custom server behaviour (e.g. failing
authentication, pre-pushed messages on connect).

Scenarios are described as a list of ``(predicate, reply_factory)`` rules:
when the server receives a frame matching the predicate, it sends the
corresponding reply. This lets each test express its expected protocol
exchange declaratively without hitting the real broker.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest
import websockets
from websockets.asyncio.server import ServerConnection, serve


ReplyFactory = Callable[[dict[str, Any]], list[dict[str, Any]] | Awaitable[list[dict[str, Any]]]]
Predicate = Callable[[dict[str, Any]], bool]


@dataclass
class FakeServer:
    host: str = "127.0.0.1"
    port: int = 0
    auth_ok: bool = True
    rules: list[tuple[Predicate, ReplyFactory]] = field(default_factory=list)
    received: list[dict[str, Any]] = field(default_factory=list)
    on_connect_messages: list[dict[str, Any]] = field(default_factory=list)

    _connections: set[ServerConnection] = field(default_factory=set)

    def url(self) -> str:
        return f"ws://{self.host}:{self.port}/echo/websocket"

    async def _handler(self, ws: ServerConnection) -> None:
        self._connections.add(ws)
        try:
            for msg in self.on_connect_messages:
                await ws.send(json.dumps(msg))
            async for raw in ws:
                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                self.received.append(frame)

                if frame.get("name") == "authenticate":
                    await ws.send(
                        json.dumps({"name": "authenticated", "msg": self.auth_ok})
                    )
                    continue

                for predicate, factory in self.rules:
                    if predicate(frame):
                        result = factory(frame)
                        if asyncio.iscoroutine(result):
                            replies = await result
                        else:
                            replies = result  # type: ignore[assignment]
                        for reply in replies:
                            await ws.send(json.dumps(reply))
                        break
        except websockets.ConnectionClosed:
            pass
        finally:
            self._connections.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        data = json.dumps(message)
        for ws in list(self._connections):
            try:
                await ws.send(data)
            except websockets.ConnectionClosed:
                pass


@asynccontextmanager
async def _start_fake_server(**kwargs):
    server = FakeServer(**kwargs)
    async with serve(server._handler, server.host, 0) as ws_server:
        sockets = ws_server.sockets
        assert sockets, "server has no listening socket"
        server.port = sockets[0].getsockname()[1]
        yield server


@pytest.fixture
async def fake_server():
    async with _start_fake_server() as server:
        yield server


@pytest.fixture
def fake_ws_factory():
    """Yields an async context manager factory:

        async with fake_ws_factory(auth_ok=False) as server:
            ...
    """
    return _start_fake_server
