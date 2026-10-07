"""
services/terraform_service.py

Runs Terraform commands against the project's /terraform directory and
returns the parsed JSON plan output.

Rules:
- Only `terraform plan -refresh-only` and `terraform show` are ever executed.
- `terraform apply` is NEVER called from this service.
- AWS credentials are sourced from the environment / IAM role — never hardcoded.
"""

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Resolve the terraform/ directory relative to this file's location:
#   backend/app/services/terraform_service.py  →  ../../..  →  project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
TERRAFORM_DIR = _PROJECT_ROOT / "terraform"
PLAN_FILE = "drift.tfplan"


class TerraformError(Exception):
    """Raised when a Terraform command exits with a non-zero status."""


def _run(args: list[str], cwd: Path) -> str:
    """Run a subprocess command and return stdout. Raises TerraformError on failure."""
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
      2. Run:  terraform plan -refresh-only -out=drift.tfplan
      3. Run:  terraform show -json drift.tfplan
      4. Parse and return the resulting JSON dict.

    Returns:
        dict: Parsed Terraform plan JSON.

    Raises:
        TerraformError: If Terraform is not installed or any command fails.
        FileNotFoundError: If the terraform/ directory does not exist.
    """
    if not TERRAFORM_DIR.is_dir():
        raise FileNotFoundError(
            f"Terraform directory not found: {TERRAFORM_DIR}. "
            "Make sure you are running the backend from the project root."
        )

    # Step 1 — create the refresh-only plan (never applies changes)
    _run(["plan", "-refresh-only", f"-out={PLAN_FILE}"], cwd=TERRAFORM_DIR)

    # Step 2 — serialise the plan to JSON
    plan_json_str = _run(["show", "-json", PLAN_FILE], cwd=TERRAFORM_DIR)

    try:
        return json.loads(plan_json_str)
    except json.JSONDecodeError as exc:
        raise TerraformError(f"Failed to parse `terraform show` JSON output: {exc}") from exc
