from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine(url: str | None = None) -> Engine:
    url = url or get_settings().database_url
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


@lru_cache
def get_sessionmaker(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(url), expire_on_commit=False, autoflush=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session; overridden in tests."""
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()


def check_database(session_factory: sessionmaker[Session] | None = None) -> tuple[bool, str | None]:
    factory = session_factory or get_sessionmaker()
    try:
        with factory() as s:
            s.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # noqa: BLE001 - report any connectivity failure
        return False, type(exc).__name__
