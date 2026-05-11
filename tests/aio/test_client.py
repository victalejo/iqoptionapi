"""Tests for the async IQ Option client (in-process fake WS server)."""

from __future__ import annotations

import asyncio

import pytest

from iqoptionapi.aio import AsyncIQOption, LoginError
from iqoptionapi.aio.exceptions import AsyncIQOptionError, RequestTimeoutError
from iqoptionapi.aio.ws import AsyncWebSocketClient


pytestmark = pytest.mark.asyncio


# We bypass the HTTP login path in tests by constructing the lower-level
# AsyncWebSocketClient directly with a fake ssid, OR by monkeypatching the
# http.async_login function.


# ---------------------------------------------------------------------------
# Low-level connection + authentication
# ---------------------------------------------------------------------------


async def test_connect_succeeds_when_server_authenticates(fake_server):
    ws = AsyncWebSocketClient(ssid="fake-ssid", wss_url=fake_server.url())
    try:
        await ws.connect(auth_timeout=2.0)
        assert fake_server.received[0]["name"] == "authenticate"
        assert fake_server.received[0]["msg"]["ssid"] == "fake-ssid"
    finally:
        await ws.close()


async def test_connect_raises_login_error_on_bad_auth(fake_ws_factory):
    async with fake_ws_factory(auth_ok=False) as server:
        ws = AsyncWebSocketClient(ssid="bad-ssid", wss_url=server.url())
        with pytest.raises(LoginError):
            await ws.connect(auth_timeout=2.0)


# ---------------------------------------------------------------------------
# Request/response correlation
# ---------------------------------------------------------------------------


async def test_get_candles_roundtrip(fake_server):
    fake_candles = [{"id": 1, "from": 100, "close": 1.234}]

    def is_get_candles(frame):
        return (
            frame.get("name") == "sendMessage"
            and isinstance(frame.get("msg"), dict)
            and frame["msg"].get("name") == "get-candles"
        )

    def reply(frame):
        return [
            {
                "name": "candles",
                "request_id": frame["request_id"],
                "msg": {"candles": fake_candles},
            }
        ]

    fake_server.rules.append((is_get_candles, reply))

    client = AsyncIQOption("user", "pw", wss_url=fake_server.url())
    # Inject a fake ssid + bypass HTTP login by constructing the WS directly.
    ws = AsyncWebSocketClient(ssid="fake", wss_url=fake_server.url())
    await ws.connect(auth_timeout=2.0)
    client._ws = ws  # noqa: SLF001 — test injection
    try:
        candles = await client.get_candles("EURUSD", 60, 50, 1_700_000_000)
        assert candles == fake_candles
        sent = fake_server.received[-1]
        body = sent["msg"]["body"]
        assert body["size"] == 60
        assert body["count"] == 50
        assert body["to"] == 1_700_000_000
    finally:
        await client.close()


async def test_request_timeout_raises(fake_server):
    # Server never replies to get-candles, so request must time out.
    def is_get_candles(frame):
        return frame.get("name") == "sendMessage"

    fake_server.rules.append((is_get_candles, lambda f: []))

    client = AsyncIQOption("u", "p", wss_url=fake_server.url())
    ws = AsyncWebSocketClient(ssid="fake", wss_url=fake_server.url())
    await ws.connect(auth_timeout=2.0)
    client._ws = ws
    try:
        with pytest.raises(RequestTimeoutError):
            await client.get_candles("EURUSD", 60, 1, 1, timeout=0.3)
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


async def test_stream_candles_yields_messages_and_unsubscribes(fake_server):
    from iqoptionapi.constants import ACTIVES

    active_id = int(ACTIVES["EURUSD"])

    client = AsyncIQOption("u", "p", wss_url=fake_server.url())
    ws = AsyncWebSocketClient(ssid="fake", wss_url=fake_server.url())
    await ws.connect(auth_timeout=2.0)
    client._ws = ws

    async def push_candles():
        await asyncio.sleep(0.05)
        for i in range(3):
            await fake_server.broadcast(
                {
                    "name": "candle-generated",
                    "msg": {
                        "active_id": active_id,
                        "size": 60,
                        "from": 1000 + i,
                        "close": 1.0 + i,
                    },
                }
            )
            await asyncio.sleep(0.01)

    try:
        push_task = asyncio.create_task(push_candles())
        collected = []
        async for candle in client.stream_candles("EURUSD", 60):
            collected.append(candle)
            if len(collected) == 3:
                break
        await push_task

        assert len(collected) == 3
        assert collected[0]["from"] == 1000
        assert collected[2]["close"] == 3.0

        # Confirm a subscribeMessage was sent and an unsubscribeMessage too.
        names = [f.get("name") for f in fake_server.received]
        assert "subscribeMessage" in names
        # Give the unsubscribe a moment to flush
        await asyncio.sleep(0.05)
        names = [f.get("name") for f in fake_server.received]
        assert "unsubscribeMessage" in names
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


async def test_heartbeat_is_echoed(fake_server):
    ws = AsyncWebSocketClient(ssid="fake", wss_url=fake_server.url())
    await ws.connect(auth_timeout=2.0)
    try:
        await fake_server.broadcast({"name": "heartbeat", "msg": "1700000000"})
        # Give the client a tick to echo back
        for _ in range(20):
            if any(f.get("name") == "heartbeat" for f in fake_server.received):
                break
            await asyncio.sleep(0.02)
        assert any(f.get("name") == "heartbeat" for f in fake_server.received)
    finally:
        await ws.close()


# ---------------------------------------------------------------------------
# Profile / balance
# ---------------------------------------------------------------------------


async def test_get_balance_picks_practice_account(fake_ws_factory):
    on_connect = [
        {"name": "profile", "msg": {"user_id": 42}},
        {
            "name": "balances",
            "msg": [
                {"id": 1, "type": 1, "amount": 100.0, "currency": "USD"},
                {"id": 2, "type": 4, "amount": 10000.0, "currency": "USD"},
            ],
        },
    ]

    async with fake_ws_factory(on_connect_messages=on_connect) as server:
        client = AsyncIQOption("u", "p", wss_url=server.url())
        ws = AsyncWebSocketClient(ssid="fake", wss_url=server.url())
        await ws.connect(auth_timeout=2.0)
        client._ws = ws
        try:
            profile = await client.get_profile()
            assert profile == {"user_id": 42}
            balance = await client.get_balance()
            assert balance["type"] == 4
            assert balance["amount"] == 10000.0
        finally:
            await client.close()


async def test_get_balance_raises_when_no_balances(fake_ws_factory):
    async with fake_ws_factory(on_connect_messages=[{"name": "balances", "msg": []}]) as server:
        client = AsyncIQOption("u", "p", wss_url=server.url())
        ws = AsyncWebSocketClient(ssid="fake", wss_url=server.url())
        await ws.connect(auth_timeout=2.0)
        client._ws = ws
        try:
            with pytest.raises(AsyncIQOptionError):
                await client.get_balance()
        finally:
            await client.close()


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


async def test_calling_methods_before_connect_raises():
    client = AsyncIQOption("u", "p")
    with pytest.raises(AsyncIQOptionError):
        await client.get_profile()
