"""
repository.py — Data access operations for drift scan history snapshots.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import DriftScanModel, ReconciliationPlanModel
from app.models.drift import DriftReport, Severity
from app.models.reconciliation import ReconciliationPlanResponse

logger = logging.getLogger(__name__)


def _calc_severity_counts(drifts: Sequence) -> tuple[int, int, int]:
    """Calculate (high_severity, medium_severity, low_severity) counts."""
    high = 0
    med = 0
    low = 0

    for d in drifts:
        sev = getattr(d, "severity", None)
        sev_str = (sev.value if hasattr(sev, "value") else str(sev or "")).upper()

        if sev_str in ("HIGH", "CRITICAL"):
            high += 1
        elif sev_str == "MEDIUM":
            med += 1
        elif sev_str == "LOW":
            low += 1

    return high, med, low


def save_drift_scan(db: Session, report: DriftReport) -> Optional[DriftScanModel]:
    """
    Persist an immutable snapshot of a successful drift scan into the database.
    Calculates severity counts and serializes the complete drift records.
    """
    try:
        high_sev, med_sev, low_sev = _calc_severity_counts(report.drifts)

        # Serialize drift records to JSON-compatible dictionaries
        drifts_json = [
            d.model_dump(mode="json") if hasattr(d, "model_dump") else dict(d)
            for d in report.drifts
        ]

        status_str = report.status.value if hasattr(report.status, "value") else str(report.status)

        scan_record = DriftScanModel(
            id=uuid.uuid4(),
            scanned_at=datetime.now(timezone.utc),
            status=status_str,
            total_drifts=report.total_drifts,
            configuration_drifts=report.configuration_drifts,
            runtime_changes=report.runtime_changes,
            high_severity=high_sev,
            medium_severity=med_sev,
            low_severity=low_sev,
            drifts=drifts_json,
        )

        db.add(scan_record)
        db.commit()
        db.refresh(scan_record)
        logger.info(
            "Persisted drift scan %s to PostgreSQL (%d total drifts).",
            scan_record.id,
            scan_record.total_drifts,
        )
        return scan_record
    except Exception as exc:
        db.rollback()
        logger.error("Failed to persist drift scan snapshot: %s", exc)
        return None


def get_drift_scans(
    db: Session,
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[DriftScanModel]]:
    """
    Retrieve paginated drift scan summaries, ordered newest first.
    Returns (total_count, scan_records).
    """
    total_count = db.scalar(select(func.count(DriftScanModel.id))) or 0

    stmt = (
        select(DriftScanModel)
        .order_by(DriftScanModel.scanned_at.desc())
        .offset(offset)
        .limit(limit)
    )
    scans = list(db.scalars(stmt).all())

    return total_count, scans


def get_drift_scan_by_id(
    db: Session,
    scan_id: uuid.UUID,
) -> Optional[DriftScanModel]:
    """
    Retrieve a specific drift scan by its UUID, including full drift records.
    """
    stmt = select(DriftScanModel).where(DriftScanModel.id == scan_id)
    return db.scalars(stmt).first()


def save_reconciliation_plan(
    db: Session,
    plan: ReconciliationPlanResponse,
    plan_path: Optional[str] = None,
) -> Optional[ReconciliationPlanModel]:
    """
    Persist a speculative reconciliation plan into PostgreSQL.
    """
    try:
        summary_dict = (
            plan.summary.model_dump(mode="json")
            if hasattr(plan.summary, "model_dump")
            else dict(plan.summary)
        )
        changes_json = [
            c.model_dump(mode="json") if hasattr(c, "model_dump") else dict(c)
            for c in plan.resource_changes
        ]

        plan_record = ReconciliationPlanModel(
            id=plan.plan_id,
            created_at=plan.generated_at,
            status=plan.status.value if hasattr(plan.status, "value") else str(plan.status),
            plan_path=plan_path,
            plan_hash=plan.plan_hash,
            expires_at=plan.expires_at,
            approved_at=plan.approved_at,
            approved_by=plan.approved_by,
            approval_comment=plan.approval_comment,
            rejected_at=plan.rejected_at,
            rejected_by=plan.rejected_by,
            rejection_reason=plan.rejection_reason,
            has_destructive_changes=plan.summary.has_destructive_changes,
            summary=summary_dict,
            resource_changes=changes_json,
        )

        db.add(plan_record)
        db.commit()
        db.refresh(plan_record)
        logger.info(
            "Persisted reconciliation plan %s (destructive=%s) to PostgreSQL.",
            plan_record.id,
            plan_record.has_destructive_changes,
        )
        return plan_record
    except Exception as exc:
        db.rollback()
        logger.error("Failed to persist reconciliation plan %s: %s", plan.plan_id, exc)
        return None


def get_reconciliation_plan_by_id(
    db: Session,
    plan_id: uuid.UUID,
) -> Optional[ReconciliationPlanModel]:
    """
    Retrieve a reconciliation plan record by UUID.
    """
    stmt = select(ReconciliationPlanModel).where(ReconciliationPlanModel.id == plan_id)
    return db.scalars(stmt).first()


def get_latest_reconciliation_plan(
    db: Session,
) -> Optional[ReconciliationPlanModel]:
    """
    Retrieve the most recently generated reconciliation plan.
    """
    stmt = (
        select(ReconciliationPlanModel)
        .order_by(ReconciliationPlanModel.created_at.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def update_plan_approval(
    db: Session,
    plan_id: uuid.UUID,
    approved_by: str,
    comment: Optional[str] = None,
    approved_at: Optional[datetime] = None,
) -> Optional[ReconciliationPlanModel]:
    """
    Record approval of a reconciliation plan in PostgreSQL.
    """
    plan_record = get_reconciliation_plan_by_id(db, plan_id)
    if plan_record is None:
        return None

    try:
        plan_record.status = "APPROVED"
        plan_record.approved_at = approved_at or datetime.now(timezone.utc)
        plan_record.approved_by = approved_by
        plan_record.approval_comment = comment
        db.commit()
        db.refresh(plan_record)
        logger.info("Recorded approval for plan %s by %s.", plan_id, approved_by)
        return plan_record
    except Exception as exc:
        db.rollback()
        logger.error("Failed to record approval for plan %s: %s", plan_id, exc)
        return None


def update_plan_rejection(
    db: Session,
    plan_id: uuid.UUID,
    rejected_by: str,
    reason: str,
    rejected_at: Optional[datetime] = None,
) -> Optional[ReconciliationPlanModel]:
    """
    Record rejection of a reconciliation plan in PostgreSQL.
    """
    plan_record = get_reconciliation_plan_by_id(db, plan_id)
    if plan_record is None:
        return None

    try:
        plan_record.status = "REJECTED"
        plan_record.rejected_at = rejected_at or datetime.now(timezone.utc)
        plan_record.rejected_by = rejected_by
        plan_record.rejection_reason = reason
        db.commit()
        db.refresh(plan_record)
        logger.info("Recorded rejection for plan %s by %s (reason: %s).", plan_id, rejected_by, reason)
        return plan_record
    except Exception as exc:
        db.rollback()
        logger.error("Failed to record rejection for plan %s: %s", plan_id, exc)
        return None


def update_plan_status(
    db: Session,
    plan_id: uuid.UUID,
    status: str,
) -> Optional[ReconciliationPlanModel]:
    """
    Update lifecycle status (e.g. EXPIRED) of a reconciliation plan in PostgreSQL.
    """
    plan_record = get_reconciliation_plan_by_id(db, plan_id)
    if plan_record is None:
        return None

    try:
        plan_record.status = status
        db.commit()
        db.refresh(plan_record)
        logger.info("Updated status for plan %s to %s.", plan_id, status)
        return plan_record
    except Exception as exc:
        db.rollback()
        logger.error("Failed to update status for plan %s: %s", plan_id, exc)
        return None
