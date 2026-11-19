"""
main.py — InfraDrift FastAPI application entry point.

Routes:
  GET /health            → liveness check
  GET /api/drift         → run terraform refresh-only plan, return report, and persist to history
  GET /api/history       → retrieve paginated scan history summaries
  GET /api/history/{id}  → retrieve a specific historical scan with full drift records
"""

import logging
import os
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path as FilePath
from typing import Optional
from uuid import UUID

from fastapi import Body, FastAPI, HTTPException, Path, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import repository, session
from app.db.models import ReconciliationPlanModel
from app.models.drift import (
    DriftCategory,
    DriftHistoryResponse,
    DriftRecord,
    DriftReport,
    DriftScanDetail,
    DriftScanSummary,
    ReportStatus,
)
from app.models.reconciliation import (
    ExecutionReadinessResponse,
    PlanApprovalRequest,
    PlanRejectionRequest,
    PlanStatus,
    PlanSummary,
    ReadinessCheckItem,
    ReconciliationPlanResponse,
    ResourceChangeRecord,
)
from app.services import drift_engine, reconciliation_service, terraform_service
from app.services.terraform_service import TerraformConcurrencyError, TerraformError

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
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
def health_check():
    """
    Standard health check.
    Returns JSON confirming the backend is running and reporting database connectivity.
    """
    return {
        "status": "ok",
        "service": "infradrift-backend",
        "version": "0.2.0",
        "database_connected": session.is_database_enabled(),
    }


@app.get("/health/live", tags=["health"])
def liveness_check():
    """
    Kubernetes liveness probe.
    Returns 200 OK as long as the Uvicorn application process is alive.
    """
    return {
        "status": "alive",
        "service": "infradrift-backend",
        "version": "0.2.0",
    }


@app.get("/health/ready", tags=["health"])
def readiness_check():
    """
    Kubernetes readiness probe.
    Returns 200 OK when ready to accept traffic.
    Verifies database connectivity if DATABASE_URL is configured.
    """
    db_enabled = session.is_database_enabled()
    db_connected = False

    if db_enabled:
        try:
            with session.get_db_session() as db:
                db.execute(text("SELECT 1"))
            db_connected = True
        except Exception as exc:
            logger.warning("Readiness probe: database ping failed: %s", exc)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "not_ready",
                    "reason": f"Database check failed: {exc}",
                    "database_configured": True,
                    "database_connected": False,
                },
            )

    return {
        "status": "ready",
        "service": "infradrift-backend",
        "version": "0.2.0",
        "database_configured": db_enabled,
        "database_connected": db_connected if db_enabled else None,
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
    except TerraformConcurrencyError as exc:
        logger.warning("Drift scan rejected due to concurrent Terraform operation: %s", exc)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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


# ---------------------------------------------------------------------------
# Safe Reconciliation Plan Routes (Phase 1: Read-Only / Plan & Review)
# ---------------------------------------------------------------------------

@app.post(
    "/api/reconciliation/plan",
    response_model=ReconciliationPlanResponse,
    tags=["reconciliation"],
)
def create_reconciliation_plan_endpoint():
    """
    Generate a fresh speculative Terraform reconciliation plan.
    Identifies resource-level actions (Create, Update, Delete, Replace, No-op),
    sanitizes sensitive data, and securely stores the plan on the backend.

    CRITICAL SAFETY RULES:
      - This endpoint NEVER runs `terraform apply` or `terraform destroy`.
      - Live AWS resources and Terraform state are strictly preserved.
      - Concurrent operations are protected by process-wide mutex.
    """
    try:
        plan_response, plan_path = reconciliation_service.create_reconciliation_plan()
    except TerraformConcurrencyError as exc:
        logger.warning("Reconciliation plan rejected due to concurrency: %s", exc)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        logger.error("Terraform directory missing for reconciliation: %s", exc)
        raise HTTPException(status_code=500, detail=f"Terraform directory not found: {exc}") from exc
    except TerraformError as exc:
        logger.error("Terraform reconciliation plan generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Terraform plan failed: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        logger.error("Terraform plan timed out: %s", exc)
        raise HTTPException(status_code=504, detail="Terraform plan timed out (>120 s).") from exc

    # Persist snapshot to PostgreSQL if available
    if session.is_database_enabled():
        try:
            with session.get_db_session() as db:
                repository.save_reconciliation_plan(db, plan_response, plan_path)
        except Exception as exc:
            logger.error("Failed to persist reconciliation plan to database: %s", exc)

    return plan_response


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is timezone-aware in UTC (normalizes SQLite naive timestamps)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _model_to_plan_response(record: ReconciliationPlanModel) -> ReconciliationPlanResponse:
    """Map a database ORM plan model to a validated ReconciliationPlanResponse."""
    db_warnings = []
    if record.has_destructive_changes:
        db_warnings.append(
            "Plan contains destructive actions (DELETE or REPLACE) that will destroy live resources."
        )
    if record.plan_path and not os.path.isfile(record.plan_path):
        db_warnings.append("Notice: Underlying binary .tfplan file is not present on disk.")

    return ReconciliationPlanResponse(
        plan_id=record.id,
        generated_at=_ensure_utc(record.created_at) or record.created_at,
        status=PlanStatus(record.status),
        summary=PlanSummary.model_validate(record.summary),
        resource_changes=[
            ResourceChangeRecord.model_validate(rc)
            for rc in (record.resource_changes or [])
        ],
        warnings=db_warnings,
        plan_hash=record.plan_hash,
        expires_at=_ensure_utc(record.expires_at),
        approved_at=_ensure_utc(record.approved_at),
        approved_by=record.approved_by,
        approval_comment=record.approval_comment,
        rejected_at=_ensure_utc(record.rejected_at),
        rejected_by=record.rejected_by,
        rejection_reason=record.rejection_reason,
    )


def _fetch_plan_or_404(plan_id: UUID) -> tuple[ReconciliationPlanResponse, Optional[str]]:
    """
    Retrieve a plan from PostgreSQL (if enabled) or disk/cache.
    Raises HTTPException 404 if not found.
    Returns (plan_response, plan_path_str).
    """
    # 1. Try PostgreSQL if enabled
    if session.is_database_enabled():
        try:
            with session.get_db_session() as db:
                record = repository.get_reconciliation_plan_by_id(db, plan_id)
                if record is not None:
                    return _model_to_plan_response(record), record.plan_path
        except Exception as exc:
            logger.warning("Could not read plan %s from DB: %s", plan_id, exc)

    # 2. Try cache / disk fallback
    cached = reconciliation_service.get_cached_plan_by_id(plan_id)
    if cached is not None:
        plan_file = terraform_service.PLANS_DIR / f"{plan_id}.tfplan"
        return cached, str(plan_file) if plan_file.is_file() else None

    raise HTTPException(
        status_code=404,
        detail=f"Reconciliation plan with ID '{plan_id}' not found.",
    )


@app.get(
    "/api/reconciliation/plan/latest",
    response_model=ReconciliationPlanResponse,
    tags=["reconciliation"],
)
def get_latest_reconciliation_plan_endpoint():
    """
    Retrieve the most recently generated reconciliation plan.
    """
    # 1. Try PostgreSQL if enabled
    if session.is_database_enabled():
        try:
            with session.get_db_session() as db:
                record = repository.get_latest_reconciliation_plan(db)
                if record is not None:
                    return _model_to_plan_response(record)
        except Exception as exc:
            logger.warning("Could not read latest plan from DB: %s", exc)

    # 2. Try cache / disk fallback
    cached = reconciliation_service.get_latest_cached_plan()
    if cached is not None:
        return cached

    raise HTTPException(
        status_code=404,
        detail="No reconciliation plan has been generated yet. Use POST /api/reconciliation/plan to generate one.",
    )


@app.get(
    "/api/reconciliation/plan/{plan_id}",
    response_model=ReconciliationPlanResponse,
    tags=["reconciliation"],
)
def get_reconciliation_plan_by_id_endpoint(
    plan_id: UUID = Path(..., description="UUID of the reconciliation plan"),
):
    """
    Retrieve full details of a specific reconciliation plan by its UUID.
    """
    plan, _ = _fetch_plan_or_404(plan_id)
    return plan


@app.post(
    "/api/reconciliation/plan/{plan_id}/approve",
    response_model=ReconciliationPlanResponse,
    tags=["reconciliation"],
)
def approve_reconciliation_plan_endpoint(
    plan_id: UUID = Path(..., description="UUID of the reconciliation plan to approve"),
    request: PlanApprovalRequest = Body(...),
):
    """
    Approve an existing PENDING_REVIEW reconciliation plan.
    Verifies that the plan file exists, matches the reviewed SHA-256 hash, and has not expired.
    Records approval audit information in PostgreSQL and backend storage.
    CRITICAL: Never applies changes or alters AWS infrastructure.
    """
    plan, plan_path = _fetch_plan_or_404(plan_id)

    # State validation
    if plan.status == PlanStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{plan_id}' has already been approved by {plan.approved_by or 'admin'} at {plan.approved_at}.",
        )
    if plan.status == PlanStatus.REJECTED:
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{plan_id}' was rejected ({plan.rejection_reason or 'No reason provided'}) and cannot be approved.",
        )
    if plan.status == PlanStatus.EXECUTED:
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{plan_id}' has already been executed.",
        )
    if plan.status == PlanStatus.EXPIRED:
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{plan_id}' has expired and cannot be approved. Please generate a fresh plan.",
        )

    # Expiration / TTL check
    if reconciliation_service.check_plan_expired(plan):
        # Update status to EXPIRED
        if session.is_database_enabled():
            try:
                with session.get_db_session() as db:
                    repository.update_plan_status(db, plan_id, "EXPIRED")
            except Exception:
                pass
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{plan_id}' has expired (24h TTL window exceeded). Please generate a fresh plan.",
        )

    # Artifact integrity verification
    tfplan_file = FilePath(plan_path) if plan_path else (terraform_service.PLANS_DIR / f"{plan_id}.tfplan")
    is_valid, err_msg = reconciliation_service.verify_plan_artifact(plan, tfplan_file)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve plan: {err_msg}",
        )

    now = datetime.now(timezone.utc)

    # Persist approval in PostgreSQL if available
    if session.is_database_enabled():
        try:
            with session.get_db_session() as db:
                repository.update_plan_approval(
                    db,
                    plan_id=plan_id,
                    approved_by=request.approved_by,
                    comment=request.comment,
                    approved_at=now,
                )
        except Exception as exc:
            logger.error("Failed to persist approval for %s in DB: %s", plan_id, exc)

    # Update in cache and disk metadata JSON
    updated_plan = reconciliation_service.approve_plan_in_cache(
        plan_id=plan_id,
        approved_by=request.approved_by,
        comment=request.comment,
        approved_at=now,
    )

    if updated_plan is not None:
        return updated_plan

    plan.status = PlanStatus.APPROVED
    plan.approved_at = now
    plan.approved_by = request.approved_by
    plan.approval_comment = request.comment
    return plan


@app.post(
    "/api/reconciliation/plan/{plan_id}/reject",
    response_model=ReconciliationPlanResponse,
    tags=["reconciliation"],
)
def reject_reconciliation_plan_endpoint(
    plan_id: UUID = Path(..., description="UUID of the reconciliation plan to reject"),
    request: PlanRejectionRequest = Body(...),
):
    """
    Explicitly reject a reconciliation plan.
    Records rejection reason and audit metadata.
    """
    plan, _ = _fetch_plan_or_404(plan_id)

    if plan.status == PlanStatus.REJECTED:
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{plan_id}' is already rejected.",
        )
    if plan.status == PlanStatus.EXECUTED:
        raise HTTPException(
            status_code=400,
            detail=f"Plan '{plan_id}' has already been executed and cannot be rejected.",
        )

    now = datetime.now(timezone.utc)

    # Persist rejection in PostgreSQL if available
    if session.is_database_enabled():
        try:
            with session.get_db_session() as db:
                repository.update_plan_rejection(
                    db,
                    plan_id=plan_id,
                    rejected_by=request.rejected_by,
                    reason=request.reason,
                    rejected_at=now,
                )
        except Exception as exc:
            logger.error("Failed to persist rejection for %s in DB: %s", plan_id, exc)

    # Update in cache and disk metadata JSON
    updated_plan = reconciliation_service.reject_plan_in_cache(
        plan_id=plan_id,
        rejected_by=request.rejected_by,
        reason=request.reason,
        rejected_at=now,
    )

    if updated_plan is not None:
        return updated_plan

    plan.status = PlanStatus.REJECTED
    plan.rejected_at = now
    plan.rejected_by = request.rejected_by
    plan.rejection_reason = request.reason
    return plan


@app.get(
    "/api/reconciliation/plan/{plan_id}/readiness",
    response_model=ExecutionReadinessResponse,
    tags=["reconciliation"],
)
def get_execution_readiness_endpoint(
    plan_id: UUID = Path(..., description="UUID of the reconciliation plan"),
):
    """
    Validate whether an approved plan meets all execution readiness requirements.
    CRITICAL: Execution is permanently locked in Phase 2A. This endpoint is inspection-only.
    """
    plan, plan_path = _fetch_plan_or_404(plan_id)
    tfplan_file = FilePath(plan_path) if plan_path else (terraform_service.PLANS_DIR / f"{plan_id}.tfplan")
    return reconciliation_service.check_execution_readiness(plan, tfplan_file)
