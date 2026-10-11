"""Shared HTTP helper with bounded retries, timeouts and rate-limit handling."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.errors import ProviderError, RateLimitedError

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 425, 500, 502, 503, 504}


async def request_with_retries(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    provider: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    json: Any = None,
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
    max_retry_after: float = 30.0,
    min_rate_limit_wait: float = 0.0,
) -> httpx.Response:
    """Request with bounded exponential backoff. Never logs query params or headers (they may hold keys).

    Non-retryable 4xx errors carry a short excerpt of the response body in ``details['body']`` so
    callers can tell, e.g., an unsupported request option from an authentication failure.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = await client.request(method, url, params=params, headers=headers, json=json)
        except httpx.TimeoutException:
            last_exc = ProviderError(f"{provider} request timed out", provider=provider, retryable=True)
            log.warning("%s timeout (attempt %s/%s)", provider, attempt + 1, max_retries + 1)
        except httpx.TransportError as exc:
            last_exc = ProviderError(
                f"{provider} network error: {type(exc).__name__}", provider=provider, retryable=True
            )
            log.warning("%s network error %s (attempt %s)", provider, type(exc).__name__, attempt + 1)
        else:
            if resp.status_code == 429:
                retry_after = _retry_after(resp)
                last_exc = RateLimitedError(
                    f"{provider} rate limit exceeded", provider=provider, retryable=True, retry_after=retry_after
                )
                if attempt < max_retries and retry_after is not None and retry_after <= max_retry_after:
                    await asyncio.sleep(max(retry_after, min_rate_limit_wait))
                    continue
                if attempt < max_retries and min_rate_limit_wait:
                    # no Retry-After: honour the provider's documented minimum spacing instead of a short backoff
                    await asyncio.sleep(max(min_rate_limit_wait, backoff_seconds * (2**attempt)))
                    continue
            elif resp.status_code in RETRYABLE_STATUS:
                last_exc = ProviderError(
                    f"{provider} returned HTTP {resp.status_code}", provider=provider, retryable=True,
                    status=resp.status_code,
                )
            elif resp.status_code >= 400:
                raise ProviderError(
                    f"{provider} returned HTTP {resp.status_code}", provider=provider, retryable=False,
                    status=resp.status_code, body=resp.text[:500],
                )
            else:
                return resp
        if attempt < max_retries:
            await asyncio.sleep(backoff_seconds * (2**attempt))
    assert last_exc is not None
    raise last_exc


async def get_with_retries(client: httpx.AsyncClient, url: str, **kwargs: Any) -> httpx.Response:
    return await request_with_retries(client, "GET", url, **kwargs)


def _retry_after(resp: httpx.Response) -> float | None:
    value = resp.headers.get("retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
