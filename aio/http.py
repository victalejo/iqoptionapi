"""Async HTTP login flow against auth.iqoption.com."""

from __future__ import annotations

from typing import Any

import aiohttp

from iqoptionapi.aio.exceptions import LoginError

DEFAULT_LOGIN_URL = "https://auth.iqoption.com/api/v2/login"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


async def async_login(
    email: str,
    password: str,
    *,
    session: aiohttp.ClientSession | None = None,
    login_url: str = DEFAULT_LOGIN_URL,
    timeout: float = 15.0,
) -> str:
    """POST credentials and return the ``ssid`` cookie value.

    Raises ``LoginError`` on any non-success (HTTP error, no ssid cookie,
    or 2FA challenge — which the MVP does not handle).

    A caller-supplied ``session`` is used as-is and not closed; otherwise
    a temporary session is created and closed before return.
    """
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession(
            headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=timeout),
        )
    assert session is not None  # for type checkers

    try:
        try:
            response = await session.post(
                login_url,
                data={"identifier": email, "password": password},
            )
        except aiohttp.ClientError as exc:
            raise LoginError(f"HTTP login request failed: {exc}") from exc

        async with response:
            payload: dict[str, Any] | None
            try:
                payload = await response.json(content_type=None)
            except (aiohttp.ContentTypeError, ValueError):
                payload = None

            if response.status != 200:
                raise LoginError(
                    f"Login failed: HTTP {response.status}: {payload!r}"
                )

            ssid = response.cookies.get("ssid")
            if ssid is None:
                # 2FA challenges come back as 200 with a verify token in body.
                if isinstance(payload, dict) and "code" in payload and payload.get(
                    "code"
                ) == "verify":
                    raise LoginError(
                        "2FA challenge required; not supported in async MVP"
                    )
                raise LoginError(
                    f"Login succeeded but no ssid cookie in response: {payload!r}"
                )
            return ssid.value
    finally:
        if own_session:
            await session.close()
