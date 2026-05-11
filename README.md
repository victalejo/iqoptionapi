# iqoptionapi

Unofficial Python wrapper for the [IQ Option](https://iqoption.com) trading
platform. Provides both a battle-tested synchronous client (binary, digital,
forex, CFD, crypto) and a new **asyncio-based client** for connection and
real-time market data.

> ⚠️ **Disclaimer.** This project is not affiliated with, endorsed by, or
> connected to IQ Option in any way. It is community-maintained and based
> on observed WebSocket / HTTP behaviour, so the protocol may change at any
> time and break the client. Trading carries financial risk: use a practice
> account first, and verify legality in your jurisdiction before using a
> real account. The authors accept no responsibility for financial loss,
> account suspension, or any other consequences of use.

## Features

- **Synchronous client** (`iqoptionapi.stable_api.IQ_Option`)
  - Login (email/password, 2FA, SSID reuse), proxy support
  - Real (USD/EUR/etc.) and practice balances; balance switching
  - Real-time candle streams over WebSocket
  - Binary, digital, forex/CFD/crypto orders with TP/SL and leverage
  - Leaderboard, traders mood, live deals, transaction history
- **Async client** (`iqoptionapi.aio.AsyncIQOption`) — *new in 0.1.0*
  - `aiohttp` + `websockets` based, no thread juggling
  - Read-only MVP: login, balance, profile, historical and streaming candles
  - Async-iterator API for candle streams
  - Proper exception hierarchy, no silent failures

## Install

```bash
# clone + install in editable mode
git clone https://github.com/victalejo/iqoptionapi.git
cd iqoptionapi

# core (sync) only
pip install -e .

# core + async client
pip install -e ".[aio]"

# everything (async + dev tools: pytest, ruff, mypy)
pip install -e ".[aio,dev]"
```

Requires Python 3.10 or newer.

## Quick start — synchronous

```python
from iqoptionapi.stable_api import IQ_Option

api = IQ_Option("your_email@example.com", "your_password")
api.connect()
api.change_balance("PRACTICE")  # don't use REAL until you're sure

candles = api.get_candles("EURUSD", interval=60, count=100,
                          endtime=api.get_server_timestamp())
print(candles[0])
```

## Quick start — async

```python
import asyncio
from iqoptionapi.aio import AsyncIQOption


async def main():
    async with AsyncIQOption("your_email@example.com", "your_password") as client:
        balance = await client.get_balance()
        print(f"Balance: {balance['amount']} {balance['currency']}")

        # Discrete history
        candles = await client.get_candles(
            active="EURUSD", size=60, count=50, endtime=1700000000,
        )
        print(f"Got {len(candles)} candles")

        # Streaming — stop after 10 candles
        n = 0
        async for candle in client.stream_candles("EURUSD", size=60):
            print(candle)
            n += 1
            if n >= 10:
                break


asyncio.run(main())
```

## When to use which client

| Use case | Sync (`IQ_Option`) | Async (`AsyncIQOption`) |
|---|---|---|
| Quick CLI scripts | ✅ | ✅ |
| Placing orders today | ✅ | ❌ (not yet) |
| Inside FastAPI / aiohttp / Discord bots | ⚠️ blocks the event loop | ✅ |
| Many concurrent candle streams | ⚠️ thread-per-stream | ✅ single loop |
| Battle-tested production code | ✅ | ⚠️ MVP, 0.1.0 |

## Async client — current scope

The 0.1.0 async client is **read-only**:

- `await client.connect()` / `await client.close()` (or use `async with`)
- `await client.get_balance()` — currently-active balance
- `await client.get_balances()` — all balances on the account
- `await client.get_profile()` — user profile
- `await client.get_candles(active, size, count, endtime)` — history
- `async for candle in client.stream_candles(active, size)` — live stream

Trading methods (`buy`, `buy_digital_spot`, `buy_order`, …) are intentionally
**not** in this release. See [`docs/superpowers/specs/`](docs/superpowers/specs/)
for the design rationale.

## Development

```bash
pip install -e ".[aio,dev]"

# Lint
ruff check .

# Tests (no network access required — uses in-process fake WS server)
pytest

# Type check the async subpackage
mypy
```

## Project layout

```
iqoptionapi/
├── api.py              # sync low-level WebSocket+HTTP client
├── stable_api.py       # sync high-level facade (IQ_Option)
├── constants.py        # active/instrument code tables
├── http/               # sync HTTP endpoints (login, 2FA, profile, ...)
├── ws/                 # sync WebSocket channels + objects
└── aio/                # async client (NEW)
    ├── client.py       # AsyncIQOption facade
    ├── http.py         # aiohttp login
    ├── ws.py           # websockets dispatcher
    └── exceptions.py
docs/superpowers/specs/ # design documents
tests/aio/              # async client tests (fake WS server)
```

## Credits

This project descends from the long lineage of community IQ Option Python
wrappers — notably the work of [Lu-Yi-Hsun](https://github.com/Lu-Yi-Hsun)
and [n1nj4z33](https://github.com/n1nj4z33) — extended here with packaging,
licensing, an async client, and tests.

## Licence

[MIT](LICENSE) © 2026 victalejo.
