"""Database engine & session management (Data layer foundation).

Targets MySQL by default (see config). The engine is created at import time but only
opens connections lazily, so the application can boot and report health even when the
database is temporarily unreachable.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings
from .logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


engine = create_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    future=True,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_connection() -> bool:
    """True if the application database answers a trivial query."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 — health probe must never raise
        logger.warning("Database connectivity check failed: %s", exc)
        return False


def ensure_database_exists() -> None:
    """Create the target MySQL database if it does not yet exist.

    No-op for non-MySQL URLs (e.g. SQLite creates the file automatically).
    """
    if not settings.is_mysql:
        return
    server = create_engine(settings.sqlalchemy_server_url, future=True, isolation_level="AUTOCOMMIT")
    try:
        with server.connect() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_db}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
        logger.info("Ensured database `%s` exists.", settings.mysql_db)
    finally:
        server.dispose()


def create_all() -> None:
    """Create every registered table (dev convenience; Alembic is the source of truth)."""
    import app.models  # noqa: F401 — ensure models are imported and registered

    Base.metadata.create_all(bind=engine)
    logger.info("Base.metadata.create_all complete (%d tables).", len(Base.metadata.tables))
