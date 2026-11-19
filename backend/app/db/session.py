"""
session.py — Database engine and session lifecycle management for InfraDrift.
Uses SQLAlchemy 2.0 with psycopg 3.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base

logger = logging.getLogger(__name__)

_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker[Session]] = None
_db_enabled: bool = False


def normalize_database_url(url: str) -> str:
    """
    Ensure the PostgreSQL URL uses the psycopg v3 dialect.
    Converts 'postgres://' or 'postgresql://' to 'postgresql+psycopg://'.
    Leaves SQLite and explicit dialects untouched.
    """
    url = url.strip()
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def is_database_enabled() -> bool:
    """Return True if a database has been successfully initialized and connected."""
    return _db_enabled and _SessionFactory is not None


def get_engine() -> Optional[Engine]:
    """Return the active SQLAlchemy engine, if configured."""
    return _engine


def init_db(engine_override: Optional[Engine] = None) -> bool:
    """
    Initialize the database engine and create tables.
    If engine_override is provided, it is used directly (useful for tests).
    If DATABASE_URL is not set, disables persistence without raising an error.
    """
    global _engine, _SessionFactory, _db_enabled

    if engine_override is not None:
        _engine = engine_override
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        Base.metadata.create_all(bind=_engine)
        _db_enabled = True
        logger.info("Database initialized via engine override.")
        return True

    raw_url = os.getenv("DATABASE_URL")
    if not raw_url or not raw_url.strip():
        logger.info("DATABASE_URL not set; PostgreSQL drift history is disabled.")
        _engine = None
        _SessionFactory = None
        _db_enabled = False
        return False

    db_url = normalize_database_url(raw_url)

    try:
        connect_args = {}
        if db_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        _engine = create_engine(
            db_url,
            echo=False,
            pool_pre_ping=True,
            connect_args=connect_args,
        )

        # Verify connection and create schema
        with _engine.connect() as conn:
            Base.metadata.create_all(bind=_engine)

        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        _db_enabled = True
        logger.info("PostgreSQL drift history database connected and schema verified.")
        return True
    except Exception as exc:
        logger.error(
            "Failed to connect to database using DATABASE_URL: %s. "
            "InfraDrift will continue with database history disabled.",
            exc,
        )
        _engine = None
        _SessionFactory = None
        _db_enabled = False
        return False


def reset_db_state() -> None:
    """Reset database state to uninitialized (used in tests)."""
    global _engine, _SessionFactory, _db_enabled
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
    _engine = None
    _SessionFactory = None
    _db_enabled = False


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager yielding a synchronous SQLAlchemy session.
    Closes the session upon exit.
    """
    if _SessionFactory is None:
        raise RuntimeError("Database session factory is not configured or database is disabled.")

    session = _SessionFactory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Optional[Session], None, None]:
    """
    FastAPI dependency that yields a database session or None if disabled.
    """
    if not is_database_enabled() or _SessionFactory is None:
        yield None
        return

    session = _SessionFactory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
