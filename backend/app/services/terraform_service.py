"""
services/terraform_service.py

Runs Terraform commands against the project's /terraform directory and
returns the parsed JSON plan output.

Safety Rules:
- Only `terraform plan` and `terraform show` are ever executed.
- `terraform apply` and `terraform destroy` are STRICTLY FORBIDDEN and blocked by code assertions.
- A process-wide lock prevents concurrent Terraform operations and state-lock conflicts.
- Reconciliation plans are saved to unique filenames and never overwrite each other.
- AWS credentials are sourced from the environment / IAM role — never hardcoded.
"""

import json
import logging
import os
import subprocess
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)

# Resolve the terraform/ directory relative to this file's location:
#   backend/app/services/terraform_service.py  →  ../../..  →  project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
TERRAFORM_DIR = _PROJECT_ROOT / "terraform"
PLANS_DIR = TERRAFORM_DIR / "plans"
PLAN_FILE = "drift.tfplan"

# Whitelist of permissible subcommands: only non-mutating plan and show operations are allowed.
# All mutating subcommands (apply, destroy, taint, untaint, import, etc.) are strictly blocked.
ALLOWED_SUBCOMMANDS = {"plan", "show", "version"}

# Mutex to prevent concurrent Terraform executions within this backend process.
# Note: This is an in-process threading.Lock. It protects against concurrent requests
# within a single Python process/worker. If running multiple backend worker processes or
# instances against the same Terraform state, cross-process locking (e.g. Terraform's
# native DynamoDB state lock or PostgreSQL advisory locks) provides cluster-wide safety.
_terraform_lock = threading.Lock()


class TerraformError(Exception):
    """Raised when a Terraform command exits with a non-zero status."""


class TerraformConcurrencyError(Exception):
    """Raised when a Terraform command cannot be executed because another is in progress."""


@contextmanager
def acquire_terraform_lock(timeout: float = 0.0) -> Generator[None, None, None]:
    """
    Context manager that acquires the process-wide Terraform lock.
    Raises TerraformConcurrencyError if lock is unavailable.
    Guarantees lock release in finally block even if operations fail.
    """
    acquired = _terraform_lock.acquire(blocking=(timeout > 0), timeout=timeout if timeout > 0 else -1)
    if not acquired:
        raise TerraformConcurrencyError(
            "A Terraform operation is already in progress. Please wait for it to complete."
        )
    try:
        from app.db import session as db_session
        with db_session.acquire_advisory_lock_if_postgres():
            yield
    finally:
        _terraform_lock.release()


def _run(args: list[str], cwd: Path) -> str:
    """Run a subprocess command and return stdout. Raises TerraformError on failure."""
    # Strict safety assertion: verify command is in the read-only whitelist
    subcmd = args[0].lower() if args else ""
    if subcmd not in ALLOWED_SUBCOMMANDS:
        raise ValueError(
            f"Execution of 'terraform {subcmd}' is strictly prohibited in InfraDrift Phase 1. "
            f"Permitted subcommands: {sorted(ALLOWED_SUBCOMMANDS)}."
        )

    cmd = ["terraform"] + args
    logger.info("Running: %s (cwd=%s)", " ".join(cmd), cwd)

    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        raise TerraformError(
            f"`{' '.join(cmd)}` exited {result.returncode}.\n"
            f"stderr: {result.stderr.strip()}"
        )

    return result.stdout


def get_refresh_plan() -> dict:
    """
    Execute a refresh-only Terraform plan and return the parsed JSON output.

    Steps:
      1. Validate that the terraform/ directory exists.
      2. Acquire the process-wide lock.
      3. Run:  terraform plan -refresh-only -out=drift.tfplan
      4. Run:  terraform show -json drift.tfplan
      5. Parse and return the resulting JSON dict.

    Returns:
        dict: Parsed Terraform plan JSON.

    Raises:
        TerraformConcurrencyError: If another Terraform operation is currently running.
        TerraformError: If Terraform is not installed or any command fails.
        FileNotFoundError: If the terraform/ directory does not exist.
    """
    if not TERRAFORM_DIR.is_dir():
        raise FileNotFoundError(
            f"Terraform directory not found: {TERRAFORM_DIR}. "
            "Make sure you are running the backend from the project root."
        )

    with acquire_terraform_lock():
        # Step 1 — create the refresh-only plan (never applies changes)
        _run(["plan", "-refresh-only", f"-out={PLAN_FILE}"], cwd=TERRAFORM_DIR)

        # Step 2 — serialise the plan to JSON
        plan_json_str = _run(["show", "-json", PLAN_FILE], cwd=TERRAFORM_DIR)

    try:
        return json.loads(plan_json_str)
    except json.JSONDecodeError as exc:
        raise TerraformError(f"Failed to parse `terraform show` JSON output: {exc}") from exc


def generate_reconciliation_plan_raw(plan_id: str) -> tuple[dict, Path]:
    """
    Execute a standard speculative Terraform plan and return (plan_json, plan_file_path).

    Steps:
      1. Validate that the terraform/ directory exists.
      2. Ensure the plans/ output directory exists.
      3. Acquire the process-wide lock.
      4. Run:  terraform plan -out=plans/{plan_id}.tfplan
      5. Run:  terraform show -json plans/{plan_id}.tfplan
      6. Parse and return the plan JSON dict and the absolute plan file Path.

    Note: This is a speculative plan. It NEVER executes `terraform apply`.
    """
    if not TERRAFORM_DIR.is_dir():
        raise FileNotFoundError(
            f"Terraform directory not found: {TERRAFORM_DIR}. "
            "Make sure you are running the backend from the project root."
        )

    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(PLANS_DIR, 0o700)
    except Exception:
        pass

    plan_rel_path = f"plans/{plan_id}.tfplan"
    full_plan_path = TERRAFORM_DIR / plan_rel_path

    # Ensure this plan file doesn't already exist (immutable, collision protection)
    if full_plan_path.exists():
        raise FileExistsError(f"Plan file already exists: {full_plan_path}")

    with acquire_terraform_lock():
        # Step 1 — create the speculative plan targeting live AWS drift
        _run(["plan", f"-out={plan_rel_path}"], cwd=TERRAFORM_DIR)

        # Set restrictive permissions on the generated binary plan file
        try:
            os.chmod(full_plan_path, 0o600)
        except Exception:
            pass

        # Step 2 — convert binary plan to JSON
        plan_json_str = _run(["show", "-json", plan_rel_path], cwd=TERRAFORM_DIR)

    try:
        plan_json = json.loads(plan_json_str)
        return plan_json, full_plan_path
    except json.JSONDecodeError as exc:
        raise TerraformError(f"Failed to parse reconciliation plan JSON output: {exc}") from exc
