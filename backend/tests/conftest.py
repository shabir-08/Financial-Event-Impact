"""Shared fixtures. The default suite makes no paid or external calls.

Database: TEST_DATABASE_URL (default: the docker-compose PostgreSQL test database). If PostgreSQL
is unreachable the suite falls back to a temporary SQLite file and PostgreSQL-only tests skip.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from datetime import date, timedelta

# Pin configuration BEFORE importing the app so cached settings never point at dev data or keys.
_PG_TEST_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://fig:fig@localhost:5433/financial_impact_graph_test")
os.environ.update({"LLM_PROVIDER": "mock", "MARKET_DATA_PROVIDER": "none", "NEWS_PROVIDER": "fixture",
                   "ANTHROPIC_API_KEY": "", "FINNHUB_API_KEY": "", "MARKET_DATA_API_KEY": "", "APP_ENV": "test"})

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402


def _pick_database_url() -> tuple[str, bool]:
    try:
        eng = create_engine(_PG_TEST_URL, pool_pre_ping=True)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        eng.dispose()
        return _PG_TEST_URL, True
    except Exception:  # noqa: BLE001
        path = os.path.join(tempfile.gettempdir(), "fig_test.sqlite")
        return f"sqlite:///{path}", False


DATABASE_URL, IS_POSTGRES = _pick_database_url()
os.environ["DATABASE_URL"] = DATABASE_URL

import app.models  # noqa: E402,F401
from app.core.config import Settings, get_settings  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.services.catalog_seed import seed_catalog  # noqa: E402
from app.services.llm.mock_provider import MockLLMProvider  # noqa: E402
from app.services.market_data.base import PriceSeries  # noqa: E402
from app.services.relationships.knowledge_base import KnowledgeBase, load_knowledge_base  # noqa: E402

get_settings.cache_clear()


def pytest_report_header(config):
    return f"test database: {'PostgreSQL' if IS_POSTGRES else 'SQLite fallback'} ({DATABASE_URL.split('@')[-1]})"


@pytest.fixture(scope="session")
def kb() -> KnowledgeBase:
    return load_knowledge_base()


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, database_url=DATABASE_URL, llm_provider="mock",
                    market_data_provider="none", news_provider="fixture", http_backoff_seconds=0.0,
                    http_max_retries=2)


@pytest.fixture
def mock_llm(kb) -> MockLLMProvider:
    return MockLLMProvider(kb)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(DATABASE_URL, pool_pre_ping=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def _truncate(engine) -> None:
    with engine.begin() as conn:
        if IS_POSTGRES:
            names = ", ".join(t.name for t in Base.metadata.sorted_tables)
            conn.execute(text(f"TRUNCATE {names} CASCADE"))
        else:
            for t in reversed(Base.metadata.sorted_tables):
                conn.execute(t.delete())


@pytest.fixture
def db(engine, session_factory, kb) -> Iterator[Session]:
    _truncate(engine)
    s = session_factory()
    seed_catalog(s, kb)
    try:
        yield s
    finally:
        s.close()
        _truncate(engine)


# ----------------------------------------------------------------- market fakes
class FakeMarketProvider:
    """TEST-ONLY provider returning deterministic synthetic series. Marked simulated=True so any
    observation derived from it is labelled simulated. Never used outside the test suite."""

    name = "yahoo_chart"  # reuse catalog symbol mappings
    simulated = True

    def __init__(self, drift_by_symbol: dict[str, float] | None = None, fail_symbols: set[str] | None = None,
                 empty_symbols: set[str] | None = None) -> None:
        self.drift = drift_by_symbol or {}
        self.fail = fail_symbols or set()
        self.empty = empty_symbols or set()
        self.calls: list[tuple[str, date, date]] = []

    async def fetch_daily(self, symbol: str, start: date, end: date) -> PriceSeries:
        from app.core.errors import ProviderError
        from app.services.market_data.base import empty_frame

        self.calls.append((symbol, start, end))
        if symbol in self.fail:
            raise ProviderError("simulated provider outage", provider=self.name, retryable=True)
        if symbol in self.empty:
            return PriceSeries(self.name, symbol, empty_frame(), notes=["no data"], simulated=True)
        days = pd.bdate_range(start, end)
        drift = self.drift.get(symbol, 0.001)
        closes = 100 * np.cumprod(np.full(len(days), 1 + drift))
        frame = pd.DataFrame({"open": closes, "high": closes, "low": closes, "close": closes,
                              "volume": np.full(len(days), 1000.0)}, index=[d.date() for d in days])
        return PriceSeries(self.name, symbol, frame, currency="USD", simulated=True,
                           notes=["SIMULATED test series"])


@pytest.fixture
def fake_market() -> FakeMarketProvider:
    return FakeMarketProvider()


def business_days_after(d: date, n: int) -> date:
    cur = d
    while n:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            n -= 1
    return cur
