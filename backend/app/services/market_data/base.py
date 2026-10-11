"""Provider-independent market-data interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

import pandas as pd


@dataclass
class PriceSeries:
    """Daily bars indexed by trading date (exchange-local), sorted ascending.

    ``frame`` has at least a ``close`` column; the index holds ``datetime.date`` values.
    """

    provider: str
    symbol: str
    frame: pd.DataFrame
    currency: str | None = None
    timezone: str | None = None
    price_field: str = "close"
    simulated: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return self.frame.empty


class MarketDataProvider(Protocol):
    name: str
    simulated: bool

    async def fetch_daily(self, symbol: str, start: date, end: date) -> PriceSeries: ...


def empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
