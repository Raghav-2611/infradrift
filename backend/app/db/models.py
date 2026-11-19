"""
models.py — SQLAlchemy ORM models for InfraDrift PostgreSQL persistence.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarative class for SQLAlchemy models."""
    pass


class DriftScanModel(Base):
    """
    Persistent snapshot of a single Terraform refresh-only drift audit scan.
    """
    __tablename__ = "drift_scans"

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    scanned_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    status = Column(String(32), nullable=False)
    total_drifts = Column(Integer, nullable=False, default=0)
    configuration_drifts = Column(Integer, nullable=False, default=0)
    runtime_changes = Column(Integer, nullable=False, default=0)
    high_severity = Column(Integer, nullable=False, default=0)
    medium_severity = Column(Integer, nullable=False, default=0)
    low_severity = Column(Integer, nullable=False, default=0)
    drifts = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )

    __table_args__ = (
        Index("idx_drift_scans_scanned_at_desc", scanned_at.desc()),
    )
