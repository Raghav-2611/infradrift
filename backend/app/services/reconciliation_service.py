"""
services/reconciliation_service.py

Orchestrates Terraform reconciliation plan generation, parses plan JSON output,
classifies resource actions (Create, Update, Delete, Replace, No-op), sanitizes
sensitive attributes, and manages plan persistence on disk and in memory.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from app.models.reconciliation import (
    ChangedAttribute,
    ExecutionReadinessResponse,
    PlanStatus,
    PlanSummary,
    ReadinessCheckItem,
    ReconciliationAction,
    ReconciliationPlanResponse,
    ResourceChangeRecord,
)
from app.services import terraform_service

logger = logging.getLogger(__name__)

# Default plan validity window before requiring a fresh plan
DEFAULT_PLAN_TTL_HOURS = 24

# Sensitive property keywords to prevent credential/secret leakage
_SENSITIVE_KEYWORDS = {
    "password",
    "secret",
    "private_key",
    "token",
    "credential",
    "auth",
    "api_key",
    "access_key",
    "cert",
    "key_data",
}

# In-memory storage for generated plans (UUID -> (ReconciliationPlanResponse, plan_path))
_PLANS_CACHE: dict[UUID, tuple[ReconciliationPlanResponse, Optional[str]]] = {}


def _has_sensitive_flag_recursive(mask: Any) -> bool:
    """Recursively check whether a sensitivity mask dict/list contains any True flag."""
    if mask is True:
        return True
    if isinstance(mask, dict):
        return any(_has_sensitive_flag_recursive(v) for v in mask.values())
    if isinstance(mask, (list, tuple, set)):
        return any(_has_sensitive_flag_recursive(v) for v in mask)
    return False


def _has_sensitive_keyword_recursive(val: Any) -> bool:
    """Recursively check whether any key name in nested dicts matches sensitive keywords."""
    if isinstance(val, dict):
        for k, v in val.items():
            if any(kw in str(k).lower() for kw in _SENSITIVE_KEYWORDS):
                return True
            if _has_sensitive_keyword_recursive(v):
                return True
    elif isinstance(val, (list, tuple, set)):
        return any(_has_sensitive_keyword_recursive(v) for v in val)
    return False


def _sanitize_structure(val: Any, sens_mask: Any = None) -> Any:
    """
    Recursively sanitize dictionaries, lists, and primitives against sensitivity masks
    and sensitive keyword patterns.
    """
    if val is None:
        return None

    # Whole-node sensitivity flag
    if sens_mask is True:
        return "(sensitive value)"

    # Nested dictionary sanitization
    if isinstance(val, dict):
        sanitized = {}
        mask_dict = sens_mask if isinstance(sens_mask, dict) else {}
        for k, v in val.items():
            k_lower = str(k).lower()
            child_mask = mask_dict.get(k)
            # If explicit sensitivity flag is set on child
            if child_mask is True:
                sanitized[k] = "(sensitive value)"
            elif isinstance(v, (dict, list)):
                sanitized[k] = _sanitize_structure(v, child_mask)
            elif any(kw in k_lower for kw in _SENSITIVE_KEYWORDS):
                sanitized[k] = "(sensitive value)"
            else:
                sanitized[k] = v
        return sanitized

    # Nested list sanitization
    if isinstance(val, list):
        sanitized_list = []
        mask_list = sens_mask if isinstance(sens_mask, list) else []
        for idx, item in enumerate(val):
            item_mask = mask_list[idx] if idx < len(mask_list) else None
            sanitized_list.append(_sanitize_structure(item, item_mask))
        return sanitized_list

    return val


def _is_sensitive_attribute(
    key: str,
    before_sens: Any = None,
    after_sens: Any = None,
    b_val: Any = None,
    a_val: Any = None,
) -> bool:
    """
    Determine if an attribute must be treated as sensitive based on keyword matching,
    Terraform top-level or recursive sensitivity masks, or nested dictionary keys.
    """
    key_lower = key.lower()
    if any(keyword in key_lower for keyword in _SENSITIVE_KEYWORDS):
        return True

    # Check top-level boolean masks
    if before_sens is True or after_sens is True:
        return True

    # Check dict-level masks
    if isinstance(before_sens, dict):
        mask = before_sens.get(key)
        if _has_sensitive_flag_recursive(mask):
            return True
    if isinstance(after_sens, dict):
        mask = after_sens.get(key)
        if _has_sensitive_flag_recursive(mask):
            return True

    # Check nested values for sensitive keys
    if _has_sensitive_keyword_recursive(b_val) or _has_sensitive_keyword_recursive(a_val):
        return True

    return False


def _classify_action(actions: list[str]) -> ReconciliationAction:
    """
    Classify Terraform action list into a standard ReconciliationAction.
    Terraform encodes actions as:
      - ["no-op"] or ["read"] -> NO_OP
      - ["create"] -> CREATE
      - ["update"] -> UPDATE
      - ["delete"] -> DELETE
      - ["delete", "create"] or ["create", "delete"] -> REPLACE
    """
    act_set = set(actions)
    if act_set in ({"no-op"}, {"read"}) or not actions:
        return ReconciliationAction.NO_OP
    if act_set == {"create"}:
        return ReconciliationAction.CREATE
    if act_set == {"update"}:
        return ReconciliationAction.UPDATE
    if act_set == {"delete"}:
        return ReconciliationAction.DELETE
    if "delete" in act_set and "create" in act_set:
        return ReconciliationAction.REPLACE
    if "delete" in act_set:
        return ReconciliationAction.DELETE
    if "create" in act_set:
        return ReconciliationAction.CREATE
    return ReconciliationAction.UPDATE


def parse_terraform_plan_json(
    plan_json: dict,
    plan_id: UUID,
    generated_at: Optional[datetime] = None,
) -> ReconciliationPlanResponse:
    """
    Parse a Terraform show -json output dict and convert it to a structured
    ReconciliationPlanResponse with resource actions, before/after diffs, and summary.
    """
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)

    raw_resource_changes = plan_json.get("resource_changes", [])
    records: list[ResourceChangeRecord] = []

    create_cnt = 0
    update_cnt = 0
    delete_cnt = 0
    replace_cnt = 0
    noop_cnt = 0

    for rc in raw_resource_changes:
        address = rc.get("address", "unknown")
        rtype = rc.get("type", "unknown")
        change = rc.get("change", {})
        actions = change.get("actions", [])
        action_reason = change.get("action_reason")

        action = _classify_action(actions)
        is_destructive = action in (ReconciliationAction.DELETE, ReconciliationAction.REPLACE)

        # Count action stats
        if action == ReconciliationAction.CREATE:
            create_cnt += 1
        elif action == ReconciliationAction.UPDATE:
            update_cnt += 1
        elif action == ReconciliationAction.DELETE:
            delete_cnt += 1
        elif action == ReconciliationAction.REPLACE:
            replace_cnt += 1
        elif action == ReconciliationAction.NO_OP:
            noop_cnt += 1

        before = change.get("before") or {}
        after = change.get("after") or {}
        before_sens = change.get("before_sensitive") or {}
        after_sens = change.get("after_sensitive") or {}

        # Attribute-level diff
        changed_attributes: list[ChangedAttribute] = []
        all_keys = set(before.keys()) | set(after.keys())

        for key in sorted(all_keys):
            b_val = before.get(key)
            a_val = after.get(key)

            if b_val != a_val:
                is_sens = _is_sensitive_attribute(key, before_sens, after_sens, b_val, a_val)
                changed_attributes.append(
                    ChangedAttribute(
                        property=key,
                        before=_sanitize_structure(b_val, before_sens.get(key) if isinstance(before_sens, dict) else before_sens) if is_sens else b_val,
                        after=_sanitize_structure(a_val, after_sens.get(key) if isinstance(after_sens, dict) else after_sens) if is_sens else a_val,
                        is_sensitive=is_sens,
                    )
                )

        # Build human-readable change description
        if action == ReconciliationAction.CREATE:
            description = "Resource will be created in AWS"
        elif action == ReconciliationAction.DELETE:
            description = "Resource will be destroyed and removed from AWS"
        elif action == ReconciliationAction.REPLACE:
            description = "Resource will be destroyed and re-created (replacement causing downtime)"
        elif action == ReconciliationAction.NO_OP:
            description = "No changes needed (infrastructure in sync)"
        else:
            if changed_attributes:
                prop_details = []
                for ca in changed_attributes[:3]:
                    if ca.is_sensitive:
                        prop_details.append(f"{ca.property} ((sensitive value) → (sensitive value))")
                    else:
                        prop_details.append(f"{ca.property} ({ca.before} → {ca.after})")
                desc_str = ", ".join(prop_details)
                if len(changed_attributes) > 3:
                    desc_str += f", +{len(changed_attributes) - 3} more"
                description = f"Update {desc_str}"
            else:
                description = "Update resource configuration"

        # Recursively sanitize full before/after dictionaries
        sanitized_before = _sanitize_structure(before, before_sens) if before else None
        sanitized_after = _sanitize_structure(after, after_sens) if after else None

        records.append(
            ResourceChangeRecord(
                address=address,
                resource_type=rtype,
                action=action,
                is_destructive=is_destructive,
                change_description=description,
                changed_attributes=changed_attributes,
                before=sanitized_before,
                after=sanitized_after,
                action_reason=action_reason,
            )
        )

    has_destructive = (delete_cnt > 0 or replace_cnt > 0)
    total_changes = create_cnt + update_cnt + delete_cnt + replace_cnt

    summary = PlanSummary(
        total_resources=len(raw_resource_changes),
        create_count=create_cnt,
        update_count=update_cnt,
        delete_count=delete_cnt,
        replace_count=replace_cnt,
        no_op_count=noop_cnt,
        total_changes=total_changes,
        has_destructive_changes=has_destructive,
    )

    warnings: list[str] = []
    if has_destructive:
        warnings.append(
            "Plan contains destructive actions (DELETE or REPLACE) that will destroy live resources."
        )
    if replace_cnt > 0:
        warnings.append(
            "One or more resources require replacement, causing resource recreation and potential downtime."
        )

    return ReconciliationPlanResponse(
        plan_id=plan_id,
        generated_at=generated_at,
        status=PlanStatus.PENDING_REVIEW,
        summary=summary,
        resource_changes=records,
        warnings=warnings,
    )


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure a datetime is timezone-aware in UTC (handles SQLite naive timestamps)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_file_sha256(file_path: Path) -> str:
    """Compute the SHA-256 hex digest of a binary plan file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def check_plan_expired(plan: ReconciliationPlanResponse) -> bool:
    """Return True if the plan's TTL window has passed."""
    now = datetime.now(timezone.utc)
    if plan.expires_at is None:
        gen_at = _ensure_utc(plan.generated_at)
        return now > (gen_at + timedelta(hours=DEFAULT_PLAN_TTL_HOURS))
    exp_at = _ensure_utc(plan.expires_at)
    return now > exp_at


def verify_plan_artifact(
    plan: ReconciliationPlanResponse,
    plan_file_path: Path,
) -> tuple[bool, Optional[str]]:
    """
    Verify that the exact .tfplan binary file exists on disk, is non-empty,
    and matches the recorded plan SHA-256 hash.
    """
    if not plan_file_path.is_file():
        return False, f"Binary plan artifact is missing from disk: {plan_file_path}"

    try:
        size = plan_file_path.stat().st_size
        if size == 0:
            return False, f"Binary plan artifact is zero bytes: {plan_file_path}"
    except Exception as exc:
        return False, f"Could not inspect plan artifact: {exc}"

    if plan.plan_hash:
        try:
            current_hash = compute_file_sha256(plan_file_path)
            if current_hash != plan.plan_hash:
                return False, (
                    f"Plan integrity hash mismatch! Expected {plan.plan_hash}, "
                    f"found {current_hash}. Plan file was modified or corrupted."
                )
        except Exception as exc:
            return False, f"Could not verify plan checksum: {exc}"

    return True, None


def create_reconciliation_plan() -> tuple[ReconciliationPlanResponse, str]:
    """
    Execute a speculative Terraform plan, parse the output, store the plan file,
    compute plan hash, and cache the result.

    Returns:
        tuple[ReconciliationPlanResponse, str]: The parsed plan and the file path.
    """
    plan_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=DEFAULT_PLAN_TTL_HOURS)

    # Step 1: Run Terraform plan and parse JSON
    plan_json, plan_file_path = terraform_service.generate_reconciliation_plan_raw(str(plan_id))

    # Step 2: Compute SHA-256 hash of the exact binary .tfplan file if present on disk
    plan_hash = compute_file_sha256(plan_file_path) if plan_file_path.is_file() else None

    # Step 3: Parse into structured Pydantic response
    response = parse_terraform_plan_json(plan_json, plan_id=plan_id, generated_at=now)
    response.plan_hash = plan_hash
    response.expires_at = expires_at

    # Step 4: Cache in memory and write metadata JSON alongside .tfplan
    plan_path_str = str(plan_file_path)
    _PLANS_CACHE[plan_id] = (response, plan_path_str)

    try:
        json_meta_path = plan_file_path.with_suffix(".json")
        json_meta_path.write_text(response.model_dump_json(indent=2), encoding="utf-8")
        try:
            os.chmod(json_meta_path, 0o600)
        except Exception:
            pass
        logger.info("Saved reconciliation plan metadata to %s (hash=%s)", json_meta_path, plan_hash)
    except Exception as exc:
        logger.warning("Could not write plan metadata json: %s", exc)

    return response, plan_path_str


def approve_plan_in_cache(
    plan_id: UUID,
    approved_by: str,
    comment: Optional[str] = None,
    approved_at: Optional[datetime] = None,
) -> Optional[ReconciliationPlanResponse]:
    """Update in-memory cache and disk metadata JSON with approval details."""
    plan = get_cached_plan_by_id(plan_id)
    if plan is None:
        return None

    approved_time = approved_at or datetime.now(timezone.utc)
    plan.status = PlanStatus.APPROVED
    plan.approved_at = approved_time
    plan.approved_by = approved_by
    plan.approval_comment = comment

    # Update cache and disk JSON
    tfplan_path = terraform_service.PLANS_DIR / f"{plan_id}.tfplan"
    _PLANS_CACHE[plan_id] = (plan, str(tfplan_path) if tfplan_path.is_file() else None)

    json_path = terraform_service.PLANS_DIR / f"{plan_id}.json"
    try:
        json_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not update plan json for approval %s: %s", plan_id, exc)

    return plan


def reject_plan_in_cache(
    plan_id: UUID,
    rejected_by: str,
    reason: str,
    rejected_at: Optional[datetime] = None,
) -> Optional[ReconciliationPlanResponse]:
    """Update in-memory cache and disk metadata JSON with rejection details."""
    plan = get_cached_plan_by_id(plan_id)
    if plan is None:
        return None

    rej_time = rejected_at or datetime.now(timezone.utc)
    plan.status = PlanStatus.REJECTED
    plan.rejected_at = rej_time
    plan.rejected_by = rejected_by
    plan.rejection_reason = reason

    # Update cache and disk JSON
    tfplan_path = terraform_service.PLANS_DIR / f"{plan_id}.tfplan"
    _PLANS_CACHE[plan_id] = (plan, str(tfplan_path) if tfplan_path.is_file() else None)

    json_path = terraform_service.PLANS_DIR / f"{plan_id}.json"
    try:
        json_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not update plan json for rejection %s: %s", plan_id, exc)

    return plan


def check_execution_readiness(
    plan: ReconciliationPlanResponse,
    plan_file_path: Optional[Path] = None,
) -> ExecutionReadinessResponse:
    """
    Evaluate whether an approved plan meets all preconditions for execution readiness.
    Note: Real execution (terraform apply) remains strictly disabled in Phase 2A.
    """
    now = datetime.now(timezone.utc)
    checks: list[ReadinessCheckItem] = []
    ineligibility_reasons: list[str] = []

    # Check 1: Approval Status
    is_approved = (plan.status == PlanStatus.APPROVED)
    if is_approved:
        checks.append(
            ReadinessCheckItem(
                name="Plan Approval Verification",
                passed=True,
                detail=f"Approved by {plan.approved_by or 'admin'} on {plan.approved_at or now}.",
            )
        )
    else:
        checks.append(
            ReadinessCheckItem(
                name="Plan Approval Verification",
                passed=False,
                detail=f"Plan is not approved (current status: {plan.status.value}). Approval is required before execution.",
            )
        )
        ineligibility_reasons.append(f"Plan status is {plan.status.value}; must be APPROVED.")

    # Check 2: Binary Plan Artifact Integrity
    tfplan_path = plan_file_path or (terraform_service.PLANS_DIR / f"{plan.plan_id}.tfplan")
    is_valid_artifact, artifact_err = verify_plan_artifact(plan, tfplan_path)
    if is_valid_artifact:
        checks.append(
            ReadinessCheckItem(
                name="Plan Artifact & Hash Integrity",
                passed=True,
                detail=f"Binary .tfplan exists ({tfplan_path.stat().st_size} bytes) and SHA-256 matches reviewed plan.",
            )
        )
    else:
        checks.append(
            ReadinessCheckItem(
                name="Plan Artifact & Hash Integrity",
                passed=False,
                detail=artifact_err or "Artifact verification failed.",
            )
        )
        ineligibility_reasons.append(artifact_err or "Plan artifact verification failed.")

    # Check 3: TTL Window & Freshness
    is_expired = check_plan_expired(plan)
    if not is_expired:
        checks.append(
            ReadinessCheckItem(
                name="Plan Freshness & TTL",
                passed=True,
                detail=f"Plan is active within the {DEFAULT_PLAN_TTL_HOURS}h window (expires at {plan.expires_at}).",
            )
        )
    else:
        checks.append(
            ReadinessCheckItem(
                name="Plan Freshness & TTL",
                passed=False,
                detail="Plan has expired. A fresh plan must be generated and reviewed.",
            )
        )
        ineligibility_reasons.append("Plan TTL exceeded. A fresh plan must be generated.")

    # Check 4: Concurrency Lock Availability
    is_locked = terraform_service._terraform_lock.locked()
    if not is_locked:
        checks.append(
            ReadinessCheckItem(
                name="Terraform Lock Availability",
                passed=True,
                detail="Terraform mutex is free. No concurrent drift scan or plan generation is running.",
            )
        )
    else:
        checks.append(
            ReadinessCheckItem(
                name="Terraform Lock Availability",
                passed=False,
                detail="Terraform lock is currently held by an active operation.",
            )
        )
        ineligibility_reasons.append("Terraform lock is currently held by another operation.")

    # Check 5: Safety Guardrail Active
    checks.append(
        ReadinessCheckItem(
            name="Phase 2A Guardrail Lock",
            passed=True,
            detail="Phase 2A read-only guard active: actual execution is permanently locked by design.",
        )
    )

    is_ready = len(ineligibility_reasons) == 0

    return ExecutionReadinessResponse(
        plan_id=plan.plan_id,
        is_ready=is_ready,
        status=plan.status,
        checks=checks,
        ineligibility_reasons=ineligibility_reasons,
        checked_at=now,
    )


def get_cached_plan_by_id(plan_id: UUID) -> Optional[ReconciliationPlanResponse]:
    """Retrieve a plan from in-memory cache or disk by plan UUID."""
    if plan_id in _PLANS_CACHE:
        resp, path_str = _PLANS_CACHE[plan_id]
        if path_str and not Path(path_str).is_file():
            if "Notice: Underlying binary .tfplan file is not present on disk." not in resp.warnings:
                resp.warnings.append("Notice: Underlying binary .tfplan file is not present on disk.")
        return resp

    # Try loading from disk
    json_path = terraform_service.PLANS_DIR / f"{plan_id}.json"
    if json_path.is_file():
        try:
            content = json.loads(json_path.read_text(encoding="utf-8"))
            parsed = ReconciliationPlanResponse.model_validate(content)
            tfplan_path = terraform_service.PLANS_DIR / f"{plan_id}.tfplan"
            if not tfplan_path.is_file():
                if "Notice: Underlying binary .tfplan file is not present on disk." not in parsed.warnings:
                    parsed.warnings.append("Notice: Underlying binary .tfplan file is not present on disk.")
            _PLANS_CACHE[plan_id] = (parsed, str(tfplan_path) if tfplan_path.is_file() else None)
            return parsed
        except Exception as exc:
            logger.warning("Failed to parse cached plan file %s: %s", json_path, exc)

    return None


def get_latest_cached_plan() -> Optional[ReconciliationPlanResponse]:
    """Retrieve the newest plan from in-memory cache or disk."""
    if _PLANS_CACHE:
        # Return plan with newest generated_at
        sorted_plans = sorted(
            [resp for resp, _ in _PLANS_CACHE.values()],
            key=lambda p: p.generated_at,
            reverse=True,
        )
        return sorted_plans[0]

    # Check disk for latest .json file
    if terraform_service.PLANS_DIR.is_dir():
        json_files = sorted(
            terraform_service.PLANS_DIR.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for jf in json_files:
            try:
                content = json.loads(jf.read_text(encoding="utf-8"))
                parsed = ReconciliationPlanResponse.model_validate(content)
                return parsed
            except Exception:
                continue

    return None
