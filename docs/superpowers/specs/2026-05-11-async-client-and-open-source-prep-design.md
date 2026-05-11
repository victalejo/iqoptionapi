# Async client + open-source housekeeping — Design

**Date:** 2026-05-11
**Status:** Approved
**Author:** victalejo (with Claude)

## Goal

Prepare the `iqoptionapi` repository for open-source distribution and add an
asyncio-based client (MVP) for connection + market data, without touching the
existing synchronous code paths.

## Motivation

The repo currently has a single initial commit, no licence, no packaging
metadata, no install instructions, and no tests. Anyone landing on the repo
cannot legally use it or easily install it. Separately, the existing client is
synchronous and thread-based — fine for simple scripts, but awkward for users
who want to consume real-time candle streams from inside an asyncio event
loop (FastAPI services, Discord bots, dashboards using `asyncio`/`aiohttp`,
ML pipelines using `asyncio`-based message brokers).

The two pieces of work go together: shipping an async client is the first
substantive contribution we want external users to see, so the repo needs
the open-source basics in place at the same time.

## Non-goals

- No trading methods in the async client (no `buy`, `sell_option`,
  `buy_digital_spot`, `buy_order`, etc.). The MVP is read-only.
- No refactor of the existing synchronous `IQ_Option` / `IQOptionAPI`. The
  sync code stays exactly as it is.
- No PyPI publishing in this iteration. Packaging metadata will be set up so
  that publishing is a one-step decision later, but no release workflow.
- No CI in this iteration.

## Scope

### Open-source housekeeping (root of repo)

| File | Purpose |
|---|---|
| `README.md` | Description, install, sync example, async example, disclaimer, credits |
| `LICENSE` | MIT, 2026, "victalejo" |
| `.gitignore` | Standard Python: `__pycache__/`, `*.pyc`, `.venv/`, `dist/`, `build/`, `*.egg-info/`, `.pytest_cache/`, `.env`, IDE-local files |
| `pyproject.toml` | PEP 621 metadata, deps, extras `[aio]` and `[dev]`, ruff + pytest config |
| `CHANGELOG.md` | "Keep a Changelog" format, initial `0.1.0` entry |

### Async client (`iqoptionapi/aio/`)

New subpackage, fully independent of the synchronous code:

```
iqoptionapi/aio/
├── __init__.py        # public exports: AsyncIQOption
├── http.py            # aiohttp-based login (auth.iqoption.com/api/v2/login)
├── ws.py              # websockets-based WebSocket connection + dispatcher
├── client.py          # high-level AsyncIQOption facade
└── exceptions.py      # AsyncIQOptionError, LoginError, ConnectionError
```

### Tests

```
tests/
├── __init__.py
└── aio/
    ├── __init__.py
    ├── conftest.py    # pytest-asyncio config + fake WS server
    └── test_client.py # login mocked, get_candles round-trip mocked
```

## Architecture

### Component overview

```
┌─────────────────────┐
│   AsyncIQOption     │  ← user-facing API (client.py)
│  (facade, asyncio)  │
└────┬───────────┬────┘
     │           │
     │           │
     ▼           ▼
┌─────────┐  ┌──────────────────┐
│ http.py │  │      ws.py       │
│ aiohttp │  │  websockets lib  │
│  login  │  │  + dispatcher    │
└─────────┘  └──────────────────┘
     │           │
     ▼           ▼
auth.iqoption.com   iqoption.com
   /api/v2/login    /echo/websocket
```

### Data flow — login

1. `AsyncIQOption.connect()` calls `http.async_login(email, password)`.
2. `async_login` POSTs to `https://auth.iqoption.com/api/v2/login` with
   `aiohttp.ClientSession` and returns the `ssid` cookie.
3. `AsyncIQOption` opens the WebSocket via `ws.AsyncWebSocketClient.connect()`.
4. Once connected, sends `{"name":"authenticate","msg":{"ssid":SSID,"protocol":3}}`.
5. Waits for a server message with `name == "authenticated"` and
   `msg == True`, otherwise raises `LoginError`.

### Data flow — request/response (e.g. `get_candles`)

The IQ Option WebSocket uses `request_id` correlation. We exploit this with
`asyncio.Future` for per-request waiting.

1. Caller awaits `client.get_candles(active, size, count, endtime)`.
2. Method generates a unique `request_id`, creates an `asyncio.Future`,
   stores it in a `pending: dict[str, Future]` map.
3. Sends `{"name":"sendMessage","msg":{"name":"get-candles","version":"2.0","body":{...}},"request_id":"<id>"}`.
4. The background dispatcher task in `ws.py` reads messages; when it sees
   `{"name":"candles","request_id":"<id>",...}` it resolves the matching
   Future with the payload.
5. Caller receives the candles list. A configurable timeout (`default 10s`)
   raises `asyncio.TimeoutError`.

### Data flow — streaming candles

1. Caller does:
   ```python
   async for candle in client.stream_candles(active, size):
       ...
   ```
2. `stream_candles` registers an `asyncio.Queue` for `(active, size)` in a
   `subscriptions: dict[tuple, Queue]` map, then sends the
   `subscribeMessage / candle-generated / <active_id>,<size>` subscription
   message expected by the server.
3. The dispatcher routes incoming `candle-generated` messages whose
   `(active_id, size)` matches an active subscription onto the corresponding
   queue.
4. The async generator yields each candle. On cancellation, the generator's
   `finally` block sends `unsubscribeMessage` and removes the queue from
   the subscriptions map.

### Background tasks

When `AsyncIQOption.connect()` returns successfully, two background tasks
are running and owned by the client:

- **Receive loop** (`ws._receive_loop`): reads messages, parses JSON,
  dispatches to either `pending` (request/response) or `subscriptions`
  (streaming) maps.
- **Heartbeat loop** (`ws._heartbeat_loop`): responds to server `heartbeat`
  messages so the server doesn't drop us. The IQ Option server sends
  `{"name":"heartbeat","msg":<timestamp>}` and expects an echo.

Both tasks are managed via an `asyncio.TaskGroup` so cancellation propagates
correctly. On `AsyncIQOption.close()`, the task group is cancelled and the
WS connection closed.

### Reconnection

Not in MVP. The dispatcher raises `ConnectionError` if the socket drops; the
caller decides whether to reconnect. (Adding back-off reconnection later is
straightforward — wrap `connect()` in a retry loop and re-establish
subscriptions.)

## Public API surface

```python
from iqoptionapi.aio import AsyncIQOption

async with AsyncIQOption(email, password) as client:
    # Connection
    await client.connect()             # also done by `async with`
    balance = await client.get_balance()
    profile = await client.get_profile()

    # Discrete history
    candles = await client.get_candles(
        active="EURUSD", size=60, count=100, endtime=1700000000,
    )

    # Streaming
    async for candle in client.stream_candles("EURUSD", size=60):
        print(candle)
```

### Method inventory (MVP)

| Method | Returns |
|---|---|
| `await client.connect()` | `None` — establishes WS + authenticates |
| `await client.close()` | `None` |
| `await client.get_balance()` | `dict` with `id`, `amount`, `currency`, `type` |
| `await client.get_balances()` | `list[dict]` |
| `await client.get_profile()` | `dict` |
| `await client.get_candles(active, size, count, endtime)` | `list[dict]` |
| `client.stream_candles(active, size)` | `AsyncIterator[dict]` |

`active` accepts the same string keys used by the sync client (e.g.
`"EURUSD"`, `"EURUSD-OTC"`) — internally translated via the existing
`iqoptionapi.constants.ACTIVES` mapping, which we reuse, not duplicate.

## Error handling

A small exception hierarchy:

- `AsyncIQOptionError(Exception)` — base
  - `LoginError` — HTTP login failed, or server returned `authenticated=False`
  - `ConnectionError` — WS dropped or could not connect
  - `RequestTimeoutError` — `request_id` did not resolve before timeout

Where errors can be surfaced from background tasks (e.g. the receive loop
encounters a fatal error), the client transitions to a "closed" state and
re-raises the error on the next user-facing call. We do **not** silently
swallow errors anywhere — this is a deliberate departure from the sync
code's bare-`except: pass` style.

## Testing strategy

Tests run with `pytest` + `pytest-asyncio` and **do not hit the network**.

1. **HTTP login**: mock with `aresponses` (or `aiohttp`'s built-in
   `TestClient`) — verify request payload and cookie extraction.
2. **WebSocket**: spin up a tiny `websockets`-based fake server inside the
   test (in-process), bind to `localhost:0`, and run scenarios:
   - Successful authenticate flow yields `client.connect()` success.
   - `authenticated=False` payload raises `LoginError`.
   - `get_candles` round-trip: client sends `get-candles`, fake server
     replies with matching `request_id`, future resolves with payload.
   - `stream_candles`: fake server pushes 3 `candle-generated` messages;
     async iterator yields all three; cancelling the iterator triggers
     `unsubscribeMessage`.
3. **Heartbeat**: fake server sends `heartbeat`; assert client echoes it
   back within 1s.

## Out-of-scope items explicitly listed (to prevent scope creep)

- Order placement (`buy`, `buy_digital_spot`, `buy_order`, `sell_option`,
  `close_position`, `cancel_order`, `change_order`).
- Leaderboard, traders mood, live deals, transaction history.
- 2FA-aware login path. (Stub the entry point; raise `LoginError("2FA
  not yet supported in async client")` if the server returns a 2FA
  challenge.)
- Proxy support.
- Auto-reconnect.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| IQ Option WebSocket protocol changes silently break the client | Tests use a fake server, so they verify our **wire format** is consistent. Integration testing against the real server is left to the user. |
| Duplicating constants/active-id mappings drifts from the sync side | Import directly from `iqoptionapi.constants` — single source of truth. |
| Bare-`except` patterns in the sync code leak into async | Linting rule (`ruff` `E722`, `BLE001`) enabled in `pyproject.toml`. |

## Future work (intentionally not in this design)

- Async trading methods (`buy`, `buy_digital`, etc.) — separate spec.
- Auto-reconnect with back-off and subscription replay.
- 2FA flow.
- Publish to PyPI.
- GitHub Actions CI.
- Migrate the existing sync `WebsocketClient` to share the parsing layer
  with the async one (deduplicate the giant `on_message` dispatch).
