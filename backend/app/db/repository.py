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

from app.db.models import DriftScanModel
from app.models.drift import DriftReport, Severity

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
