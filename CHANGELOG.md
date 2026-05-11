# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-05-11

### Added
- **`iqoptionapi.aio` subpackage**: asyncio-based client for connection and
  market data.
  - `AsyncIQOption` facade with `connect`, `close`, `get_balance`,
    `get_balances`, `get_profile`, `get_candles`, `stream_candles`.
  - `aiohttp`-based login flow against `auth.iqoption.com`.
  - `websockets`-based WebSocket dispatcher with `request_id` correlation
    via `asyncio.Future` and pub/sub streaming via `asyncio.Queue`.
  - Custom exception hierarchy (`AsyncIQOptionError`, `LoginError`,
    `ConnectionError`, `RequestTimeoutError`) — no silent failures.
- Open-source housekeeping: `README.md`, `LICENSE` (MIT), `.gitignore`,
  `pyproject.toml` (PEP 621), `CHANGELOG.md`.
- Test suite (`tests/aio/`) with an in-process fake WebSocket server —
  exercises login, candles round-trip, streaming, and heartbeat without
  hitting the real broker.

### Notes
- The synchronous `IQ_Option` / `IQOptionAPI` is unchanged.
- The async client is **read-only** in this release; no trading methods.

[0.1.0]: https://github.com/victalejo/iqoptionapi/releases/tag/v0.1.0
