"""
main.py — InfraDrift FastAPI application entry point.

Routes:
  GET /health      → liveness check
  GET /api/drift   → run terraform refresh-only plan and return drift report
"""

import logging
import subprocess
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models.drift import DriftReport, ReportStatus
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
    yield
    logger.info("InfraDrift backend shutting down.")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="InfraDrift API",
    description="Detect infrastructure drift between Terraform desired state and real AWS state.",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow local frontend dev server to call the API (will be tightened later)
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
    Returns a simple JSON payload confirming the backend is running.
    """
    return {
        "status": "ok",
        "service": "infradrift-backend",
        "version": "0.1.0",
    }


@app.get("/api/drift", response_model=DriftReport, tags=["drift"])
def get_drift():
    """
    Run a Terraform refresh-only plan and return a structured drift report.

    Steps:
      1. Execute `terraform plan -refresh-only -out=drift.tfplan`
      2. Execute `terraform show -json drift.tfplan`
      3. Analyse the JSON plan for resource drift.
      4. Return a DriftReport.

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

    report_status = (
        ReportStatus.DRIFT_DETECTED if drift_records else ReportStatus.NO_DRIFT
    )

    return DriftReport(
        total_drifts=len(drift_records),
        status=report_status,
        drifts=drift_records,
    )
