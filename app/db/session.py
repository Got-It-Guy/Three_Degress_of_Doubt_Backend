from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _is_sqlite_url(database_url: str) -> bool:
    return database_url.startswith("sqlite")


@lru_cache
def get_engine(database_url: str | None = None) -> Engine:
    settings = get_settings()
    resolved_url = database_url or settings.database_url
    connect_args = {"check_same_thread": False} if _is_sqlite_url(resolved_url) else {}
    return create_engine(
        resolved_url,
        pool_pre_ping=not _is_sqlite_url(resolved_url),
        future=True,
        connect_args=connect_args,
    )


@lru_cache
def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    engine = get_engine(database_url)
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


engine = get_engine()
SessionLocal = get_session_factory()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
