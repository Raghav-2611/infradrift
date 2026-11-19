"""
models.py — SQLAlchemy ORM models for InfraDrift PostgreSQL persistence.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
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


class ReconciliationPlanModel(Base):
    """
    Persistent record of a speculative Terraform reconciliation plan.
    Stores metadata, summary, changes diff, and the path to the plan file.
    """
    __tablename__ = "reconciliation_plans"

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    status = Column(String(32), nullable=False, default="PENDING_REVIEW")
    plan_path = Column(String(512), nullable=True)
    plan_hash = Column(String(64), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(String(128), nullable=True)
    approval_comment = Column(String(512), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    rejected_by = Column(String(128), nullable=True)
    rejection_reason = Column(String(512), nullable=True)
    has_destructive_changes = Column(Boolean, nullable=False, default=False)
    summary = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    resource_changes = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )

    __table_args__ = (
        Index("idx_reconciliation_plans_created_at_desc", created_at.desc()),
    )
