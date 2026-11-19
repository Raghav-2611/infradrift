"""
session.py — Database engine and session lifecycle management for InfraDrift.
Uses SQLAlchemy 2.0 with psycopg 3.
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base

logger = logging.getLogger(__name__)

_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker[Session]] = None
_db_enabled: bool = False
_last_db_error: Optional[str] = None


def _sanitize_error_message(msg: str) -> str:
    """
    Remove any password from connection error messages to prevent accidental exposure.
    Matches standard URI patterns like postgresql://user:pass@host... and masks the pass.
    """
    if not msg:
        return ""
    # Mask password in URL format ://user:pass@
    sanitized = re.sub(r"://([^:@\s]+):([^@\s]+)@", r"://\1:***@", msg)
    # Mask password= in libpq / connection style strings
    sanitized = re.sub(r"password=\S+", "password=***", sanitized)
    return sanitized


def load_runtime_env() -> None:
    """
    Safely load environment variables from runtime environment files.
    Searches candidate paths in priority order:
      1. backend/.env.runtime
      2. .env.runtime
      3. backend/.env
      4. .env
    Supports:
      - Plain KEY=VALUE
      - 'export KEY=VALUE'
      - Quoted values ("value" or 'value')
      - Comments and blank lines
    Never logs, prints, or exposes variable values.
    """
    candidates = [
        Path.cwd() / "backend" / ".env.runtime",
        Path.cwd() / ".env.runtime",
        Path(__file__).resolve().parent.parent.parent / ".env.runtime",
        Path(__file__).resolve().parent.parent.parent.parent / ".env.runtime",
        Path.cwd() / "backend" / ".env",
        Path.cwd() / ".env",
    ]

    loaded_file = None
    for candidate in candidates:
        if candidate.is_file():
            loaded_file = candidate
            break

    if loaded_file is None:
        return

    try:
        with open(loaded_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Handle leading 'export '
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" in line:
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip()
                    # Strip matching surrounding quotes
                    if (val.startswith('"') and val.endswith('"')) or (
                        val.startswith("'") and val.endswith("'")
                    ):
                        val = val[1:-1]
                    # Only inject if not already set or if empty
                    if key and (key not in os.environ or not os.environ[key].strip()):
                        os.environ[key] = val
        logger.info("Loaded runtime environment from %s", loaded_file.name)
    except Exception as exc:
        logger.warning(
            "Could not read runtime environment from %s: %s",
            loaded_file.name,
            _sanitize_error_message(str(exc)),
        )


def normalize_database_url(url: str) -> str:
    """
    Ensure the PostgreSQL URL uses the psycopg v3 dialect.
    Converts 'postgres://' or 'postgresql://' to 'postgresql+psycopg://'.
    Leaves SQLite and explicit dialects untouched.
    Safely strips whitespace and surrounding quotation marks.
    """
    url = url.strip().strip("'\"")
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def is_database_enabled() -> bool:
    """
    Return True if a database has been successfully initialized and connected.
    If not yet initialized and DATABASE_URL is present (or in .env.runtime),
    attempts initialization lazily.
    """
    global _db_enabled, _SessionFactory
    if not _db_enabled or _SessionFactory is None:
        raw = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
        if not raw or not raw.strip():
            load_runtime_env()
            raw = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
        if raw and raw.strip():
            init_db()
    return _db_enabled and _SessionFactory is not None


def get_engine() -> Optional[Engine]:
    """Return the active SQLAlchemy engine, if configured."""
    return _engine


def get_last_error() -> Optional[str]:
    """Return the sanitized last database connection error, if any."""
    return _last_db_error


def init_db(engine_override: Optional[Engine] = None) -> bool:
    """
    Initialize the database engine and create tables.
    If engine_override is provided, it is used directly (useful for tests).
    If DATABASE_URL is not set, checks .env.runtime, and if still absent disables persistence.
    """
    global _engine, _SessionFactory, _db_enabled, _last_db_error

    if engine_override is not None:
        _engine = engine_override
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        Base.metadata.create_all(bind=_engine)
        _db_enabled = True
        _last_db_error = None
        logger.info("Database initialized via engine override.")
        return True

    # Check and load runtime env file if DATABASE_URL not yet set
    raw_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not raw_url or not raw_url.strip():
        load_runtime_env()
        raw_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")

    if not raw_url or not raw_url.strip():
        logger.info("DATABASE_URL not set; PostgreSQL drift history is disabled.")
        _engine = None
        _SessionFactory = None
        _db_enabled = False
        _last_db_error = "DATABASE_URL not configured"
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

        # Verify active connection with SELECT 1 ping
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # Verify/create schema idempotently (preserves existing data)
        Base.metadata.create_all(bind=_engine)

        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        _db_enabled = True
        _last_db_error = None
        logger.info("PostgreSQL drift history database connected and schema verified.")
        return True
    except Exception as exc:
        safe_msg = _sanitize_error_message(str(exc))
        logger.error(
            "Failed to connect to database using DATABASE_URL: %s. "
            "InfraDrift will continue with database history disabled.",
            safe_msg,
        )
        _engine = None
        _SessionFactory = None
        _db_enabled = False
        _last_db_error = safe_msg
        return False


def reset_db_state() -> None:
    """Reset database state to uninitialized (used in tests)."""
    global _engine, _SessionFactory, _db_enabled, _last_db_error
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
    _engine = None
    _SessionFactory = None
    _db_enabled = False
    _last_db_error = None


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


# Fixed 64-bit advisory lock key for InfraDrift Terraform operations:
# ASCII 'InfraDrf' as 64-bit integer
TERRAFORM_PG_ADVISORY_LOCK_ID = 5289943485747683942


@contextmanager
def acquire_advisory_lock_if_postgres() -> Generator[None, None, None]:
    """
    Acquire a PostgreSQL advisory lock if connected to a PostgreSQL database.
    Provides distributed mutual exclusion across multiple worker processes.
    In SQLite or when DB is disabled, yields safely without error.
    """
    engine = get_engine()
    if engine is None or engine.dialect.name != "postgresql":
        yield
        return

    conn = engine.connect()
    try:
        acquired = conn.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": TERRAFORM_PG_ADVISORY_LOCK_ID},
        ).scalar()
        if not acquired:
            conn.close()
            from app.services.terraform_service import TerraformConcurrencyError
            raise TerraformConcurrencyError(
                "A Terraform operation is already in progress on another worker (PostgreSQL advisory lock held)."
            )
        try:
            yield
        finally:
            try:
                conn.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": TERRAFORM_PG_ADVISORY_LOCK_ID},
                )
            except Exception as exc:
                logger.warning("Error releasing PostgreSQL advisory lock: %s", exc)
    finally:
        conn.close()
