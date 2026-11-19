"""
main.py — InfraDrift FastAPI application entry point.

Routes:
  GET /health            → liveness check
  GET /api/drift         → run terraform refresh-only plan, return report, and persist to history
  GET /api/history       → retrieve paginated scan history summaries
  GET /api/history/{id}  → retrieve a specific historical scan with full drift records
"""

import logging
import subprocess
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware

from app.db import repository, session
from app.models.drift import (
    DriftCategory,
    DriftHistoryResponse,
    DriftRecord,
    DriftReport,
    DriftScanDetail,
    DriftScanSummary,
    ReportStatus,
)
from app.services import drift_engine, terraform_service
from app.services.terraform_service import TerraformError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("InfraDrift backend starting up.")
    # Attempt database connection; fails gracefully if DATABASE_URL is unset
    session.init_db()
    yield
    logger.info("InfraDrift backend shutting down.")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="InfraDrift API",
    description="Detect infrastructure drift between Terraform desired state and real AWS state.",
    version="0.2.0",
    lifespan=lifespan,
)

# Allow frontend dev server and clients to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
def health_check():
    """
    Liveness check.
    Returns JSON confirming the backend is running and reporting database connectivity.
    """
    return {
        "status": "ok",
        "service": "infradrift-backend",
        "version": "0.2.0",
        "database_connected": session.is_database_enabled(),
    }


@app.get("/api/drift", response_model=DriftReport, tags=["drift"])
def get_drift():
    """
    Run a Terraform refresh-only plan, return a structured drift report,
    and persist an immutable snapshot to PostgreSQL if configured.

    Steps:
      1. Execute `terraform plan -refresh-only -out=drift.tfplan`
      2. Execute `terraform show -json drift.tfplan`
      3. Analyse the JSON plan for resource drift.
      4. Persist scan snapshot to PostgreSQL (if enabled).
      5. Return a DriftReport.

    Note: This endpoint NEVER runs `terraform apply`.
    """
    # ---- Run Terraform -------------------------------------------------------
    try:
        plan_json = terraform_service.get_refresh_plan()
    except FileNotFoundError as exc:
        logger.error("Terraform directory missing: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Terraform directory not found: {exc}",
        ) from exc
    except TerraformError as exc:
        logger.error("Terraform command failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Terraform command failed: {exc}",
        ) from exc
    except FileNotFoundError:
        # terraform binary itself is missing
        raise HTTPException(
            status_code=500,
            detail=(
                "Terraform is not installed or not on PATH. "
                "Install it from https://developer.hashicorp.com/terraform/install"
            ),
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Terraform plan timed out (>120 s). Check AWS connectivity.",
        )

    # ---- Analyse -------------------------------------------------------------
    drift_records = drift_engine.analyse_plan(plan_json)

    cfg_count = sum(
        1 for r in drift_records if r.category == DriftCategory.CONFIGURATION_DRIFT
    )
    rnt_count = sum(
        1 for r in drift_records
        if r.category in (DriftCategory.RUNTIME_STATE_CHANGE, DriftCategory.DEPENDENCY_CHANGE)
    )

    report_status = (
        ReportStatus.DRIFT_DETECTED if drift_records else ReportStatus.NO_DRIFT
    )

    report = DriftReport(
        total_drifts=len(drift_records),
        configuration_drifts=cfg_count,
        runtime_changes=rnt_count,
        status=report_status,
        drifts=drift_records,
    )

    # ---- Persist snapshot (non-blocking for live detection) -------------------
    if session.is_database_enabled():
        try:
            with session.get_db_session() as db:
                saved = repository.save_drift_scan(db, report)
                if saved is not None:
                    report.scan_id = saved.id
                    report.scanned_at = saved.scanned_at
        except Exception as exc:
            logger.error("Database persistence failed, but live drift response preserved: %s", exc)

    return report


@app.get("/api/history", response_model=DriftHistoryResponse, tags=["history"])
def get_history(
    limit: int = Query(default=20, ge=1, le=100, description="Maximum number of scans to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
):
    """
    Retrieve paginated drift scan history summaries, ordered newest first.
    """
    if not session.is_database_enabled():
        raise HTTPException(
            status_code=503,
            detail="Database history is disabled. DATABASE_URL environment variable is not configured.",
        )

    try:
        with session.get_db_session() as db:
            total_count, records = repository.get_drift_scans(db, limit=limit, offset=offset)

            summaries = [
                DriftScanSummary(
                    id=s.id,
                    scanned_at=s.scanned_at,
                    status=ReportStatus(s.status),
                    total_drifts=s.total_drifts,
                    configuration_drifts=s.configuration_drifts,
                    runtime_changes=s.runtime_changes,
                    high_severity=s.high_severity,
                    medium_severity=s.medium_severity,
                    low_severity=s.low_severity,
                )
                for s in records
            ]

            return DriftHistoryResponse(
                total_scans=total_count,
                limit=limit,
                offset=offset,
                scans=summaries,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch drift history: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve drift scan history.")


@app.get("/api/history/{scan_id}", response_model=DriftScanDetail, tags=["history"])
def get_history_detail(
    scan_id: UUID = Path(..., description="UUID of the historical drift scan"),
):
    """
    Retrieve full details of a specific historical drift scan, including all original drift records.
    """
    if not session.is_database_enabled():
        raise HTTPException(
            status_code=503,
            detail="Database history is disabled. DATABASE_URL environment variable is not configured.",
        )

    try:
        with session.get_db_session() as db:
            scan = repository.get_drift_scan_by_id(db, scan_id)
            if scan is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Drift scan with ID '{scan_id}' not found.",
                )

            records_list = [
                DriftRecord.model_validate(d) for d in (scan.drifts or [])
            ]

            return DriftScanDetail(
                id=scan.id,
                scanned_at=scan.scanned_at,
                status=ReportStatus(scan.status),
                total_drifts=scan.total_drifts,
                configuration_drifts=scan.configuration_drifts,
                runtime_changes=scan.runtime_changes,
                high_severity=scan.high_severity,
                medium_severity=scan.medium_severity,
                low_severity=scan.low_severity,
                drifts=records_list,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch historical scan detail for %s: %s", scan_id, exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve drift scan details.")
