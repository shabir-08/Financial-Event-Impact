"""Alpha Vantage adapter (MARKET_DATA_PROVIDER=alphavantage, needs MARKET_DATA_API_KEY).

Supports US equities/ETFs via TIME_SERIES_DAILY and FX pairs via FX_DAILY (catalog symbols of
the form ``FX:USD/INR``). On the free tier only the most recent ~100 sessions ("compact") are
returned, so long-ago historical windows will be UNAVAILABLE. Rate-limit / premium notices,
which Alpha Vantage returns with HTTP 200, are raised as provider errors.
"""

from __future__ import annotations

from datetime import date

import httpx
import pandas as pd

from app.core.config import Settings
from app.core.errors import ConfigurationError, ProviderError, RateLimitedError
from app.services.http import get_with_retries
from app.services.market_data.base import PriceSeries, empty_frame

AV_URL = "https://www.alphavantage.co/query"


class AlphaVantageProvider:
    name = "alphavantage"
    simulated = False

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if not settings.market_data_api_key or not settings.market_data_api_key.get_secret_value():
            raise ConfigurationError("MARKET_DATA_PROVIDER=alphavantage but MARKET_DATA_API_KEY is not set",
                                     details={"integration": "market_data", "provider": "alphavantage"})
        self.settings = settings
        self._client = client

    async def fetch_daily(self, symbol: str, start: date, end: date) -> PriceSeries:
        key = self.settings.market_data_api_key.get_secret_value()
        if symbol.startswith("FX:"):
            base, quote = symbol[3:].split("/")
            params = {"function": "FX_DAILY", "from_symbol": base, "to_symbol": quote, "outputsize": "compact"}
        else:
            params = {"function": "TIME_SERIES_DAILY", "symbol": symbol, "outputsize": "compact"}
        params["apikey"] = key
        client = self._client or httpx.AsyncClient(timeout=self.settings.http_timeout_seconds)
        try:
            resp = await get_with_retries(client, AV_URL, provider=self.name, params=params,
                                          max_retries=self.settings.http_max_retries,
                                          backoff_seconds=self.settings.http_backoff_seconds)
        finally:
            if self._client is None:
                await client.aclose()
        return self.parse(symbol, resp.json(), start, end)

    def parse(self, symbol: str, payload: dict, start: date, end: date) -> PriceSeries:
        if "Note" in payload or "Information" in payload:
            msg = str(payload.get("Note") or payload.get("Information"))[:200]
            raise RateLimitedError(f"Alpha Vantage limit/premium notice: {msg}", provider=self.name, retryable=False)
        if "Error Message" in payload:
            return PriceSeries(self.name, symbol, empty_frame(), notes=["symbol not recognised by provider"])
        series_key = next((k for k in payload if k.startswith("Time Series")), None)
        if series_key is None:
            raise ProviderError("Alpha Vantage response missing time series", provider=self.name)
        rows = payload[series_key]
        frame = pd.DataFrame.from_dict(rows, orient="index").rename(columns=lambda c: c.split(". ", 1)[-1])
        frame.index = [date.fromisoformat(d) for d in frame.index]
        frame = frame.apply(pd.to_numeric, errors="coerce").sort_index()
        frame = frame[(frame.index >= start) & (frame.index <= end)]
        notes = ["unadjusted close (TIME_SERIES_DAILY / FX_DAILY)"]
        if rows and min(date.fromisoformat(d) for d in rows) > start:
            notes.append("provider history (compact) starts after requested start date")
        return PriceSeries(self.name, symbol, frame, timezone="America/New_York", notes=notes)
