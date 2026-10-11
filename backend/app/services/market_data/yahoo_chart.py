"""Yahoo Finance *chart* endpoint adapter (opt-in: MARKET_DATA_PROVIDER=yahoo_chart).

This endpoint is unofficial and undocumented; Yahoo's terms restrict use of its data. It is
provided for research/demo use only - verify licensing before any other use. Coverage is broad
(global equities, indices, FX, futures) but symbols differ from exchange tickers (e.g. INR=X,
^NSEI, BZ=F) and some markets (e.g. Moscow Exchange) may return no data.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

from app.core.config import Settings
from app.core.errors import ProviderError
from app.services.http import get_with_retries
from app.services.market_data.base import PriceSeries, empty_frame

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


class YahooChartProvider:
    name = "yahoo_chart"
    simulated = False

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client

    async def fetch_daily(self, symbol: str, start: date, end: date) -> PriceSeries:
        p1 = int(datetime.combine(start, time.min, tzinfo=timezone.utc).timestamp())
        p2 = int(datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc).timestamp())
        client = self._client or httpx.AsyncClient(timeout=self.settings.http_timeout_seconds)
        try:
            resp = await get_with_retries(
                client, CHART_URL.format(symbol=symbol), provider=self.name,
                params={"period1": p1, "period2": p2, "interval": "1d", "events": "div,splits"},
                headers={"User-Agent": "Mozilla/5.0 (financial-impact-graph research)"},
                max_retries=self.settings.http_max_retries, backoff_seconds=self.settings.http_backoff_seconds,
            )
        except ProviderError as exc:
            if exc.details.get("status") == 404:
                return PriceSeries(self.name, symbol, empty_frame(), notes=["symbol not found at provider"])
            raise
        finally:
            if self._client is None:
                await client.aclose()
        return self.parse(symbol, resp.json())

    def parse(self, symbol: str, payload: dict) -> PriceSeries:
        chart = (payload or {}).get("chart") or {}
        if chart.get("error"):
            return PriceSeries(self.name, symbol, empty_frame(), notes=[f"provider error: {chart['error']}"])
        results = chart.get("result") or []
        if not results:
            return PriceSeries(self.name, symbol, empty_frame(), notes=["provider returned no result"])
        r = results[0]
        meta = r.get("meta") or {}
        tz_name = meta.get("exchangeTimezoneName") or "UTC"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:  # noqa: BLE001 - unknown tz names fall back to UTC
            tz = ZoneInfo("UTC")
        stamps = r.get("timestamp") or []
        quote = ((r.get("indicators") or {}).get("quote") or [{}])[0]
        adj = ((r.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose")
        if not stamps:
            return PriceSeries(self.name, symbol, empty_frame(), meta.get("currency"), tz_name,
                               notes=["no observations in requested range"])
        dates = [datetime.fromtimestamp(s, tz=timezone.utc).astimezone(tz).date() for s in stamps]
        frame = pd.DataFrame(
            {
                "open": quote.get("open"), "high": quote.get("high"), "low": quote.get("low"),
                "close": adj if adj and len(adj) == len(stamps) else quote.get("close"),
                "raw_close": quote.get("close"), "volume": quote.get("volume"),
            },
            index=dates,
        )
        frame = frame[~frame.index.duplicated(keep="last")].dropna(subset=["close"]).sort_index()
        notes = []
        if adj:
            notes.append("close = split/dividend-adjusted close")
        return PriceSeries(self.name, symbol, frame, meta.get("currency"), tz_name,
                           "adjclose" if adj else "close", notes=notes)
