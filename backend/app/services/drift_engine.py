"""
services/drift_engine.py

Analyses a Terraform refresh-only plan JSON and extracts every attribute
where the real AWS state differs from Terraform's desired/known state.

How a refresh-only plan encodes drift:
  plan["resource_drift"] → list of resources where live state ≠ last-known state.
  Each resource entry has:
    - "address"        → e.g. "aws_instance.drift_demo"
    - "type"           → e.g. "aws_instance"
    - "change.before"  → attributes Terraform has stored in state (desired)
    - "change.after"   → attributes freshly read from AWS (actual)

A drift exists for every key where before[key] != after[key].

Classification strategy
-----------------------
Each differing attribute is independently classified into one of three categories:

  CONFIGURATION_DRIFT    — a meaningful infrastructure setting was changed outside
                           Terraform (e.g. instance_type, AMI, security groups).

  RUNTIME_STATE_CHANGE   — a transient value that changes automatically based on
                           the instance's power/lifecycle state (e.g. instance_state,
                           public_ip when the instance is stopped, public_dns).

  DEPENDENCY_CHANGE      — an attribute that changed solely because another attribute
                           changed (e.g. ebs_optimized forced by instance type family).

The classification is deterministic and table-driven so it is easy to extend.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.models.drift import DriftCategory, DriftRecord, DriftStatus, Severity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classification tables
# ---------------------------------------------------------------------------

# Properties that represent genuine configuration changes
_CONFIGURATION_PROPERTIES: dict[str, tuple[Severity, str]] = {
    # instance
    "instance_type": (
        Severity.HIGH,
        "EC2 instance type differs from the Terraform desired configuration.",
    ),
    "ami": (
        Severity.HIGH,
        "EC2 AMI differs from the Terraform desired configuration.",
    ),
    "associate_public_ip_address": (
        Severity.MEDIUM,
        "Public IP association setting differs from the Terraform desired configuration.",
    ),
    # networking
    "vpc_security_group_ids": (
        Severity.HIGH,
        "Security group assignment differs from the Terraform desired configuration.",
    ),
    "security_groups": (
        Severity.HIGH,
        "Security group names differ from the Terraform desired configuration.",
    ),
    "subnet_id": (
        Severity.HIGH,
        "Subnet placement differs from the Terraform desired configuration.",
    ),
    "private_ip": (
        Severity.MEDIUM,
        "Private IP address differs from the Terraform desired configuration.",
    ),
    # IAM
    "iam_instance_profile": (
        Severity.CRITICAL,
        "IAM instance profile differs from the Terraform desired configuration.",
    ),
    # storage
    "root_block_device": (
        Severity.HIGH,
        "Root block device configuration differs from the Terraform desired state.",
    ),
    "ebs_block_device": (
        Severity.HIGH,
        "EBS block device configuration differs from the Terraform desired state.",
    ),
    # metadata
    "disable_api_termination": (
        Severity.CRITICAL,
        "API termination protection setting differs from the Terraform desired configuration.",
    ),
    "monitoring": (
        Severity.LOW,
        "Detailed monitoring setting differs from the Terraform desired configuration.",
    ),
    # tags
    "tags": (
        Severity.LOW,
        "Resource tags differ from the Terraform desired configuration.",
    ),
    "tags_all": (
        Severity.LOW,
        "Effective resource tags (including inherited) differ from the Terraform desired state.",
    ),
    "volume_tags": (
        Severity.LOW,
        "EBS volume tags differ from the Terraform desired configuration.",
    ),
}

# Properties whose values change automatically based on instance lifecycle state.
# These are not actionable configuration drift — they are side-effects of the
# instance being stopped, started, or replaced.
_RUNTIME_PROPERTIES: dict[str, str] = {
    "instance_state": (
        "The EC2 instance power state changed; this is a runtime condition, "
        "not a configuration change."
    ),
    "public_ip": (
        "Public IP becomes empty when the instance is stopped; "
        "this is a runtime-dependent value, not a configuration drift."
    ),
    "public_dns": (
        "Public DNS becomes empty when the instance is stopped; "
        "this is a runtime-dependent value, not a configuration drift."
    ),
    "ipv6_addresses": (
        "IPv6 address list changes with instance lifecycle; "
        "this is a runtime-dependent value."
    ),
    "password_data": (
        "Windows password data is runtime-generated and not a configuration change."
    ),
}

# Properties that change as a side-effect of another resource attribute changing.
# e.g. ebs_optimized is forced on/off by certain instance type families.
_DEPENDENCY_PROPERTIES: dict[str, str] = {
    "ebs_optimized": (
        "EBS optimisation is automatically controlled by the instance type family; "
        "this change is a side-effect of the instance_type drift, not an "
        "independent configuration change."
    ),
    "cpu_core_count": (
        "CPU core count is derived from the instance type and is not independently configurable."
    ),
    "cpu_threads_per_core": (
        "CPU threads per core is derived from the instance type and is not independently configurable."
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_str(value: Any) -> str:
    """Convert any Python value to a compact, readable string."""
    if isinstance(value, (list, dict)):
        return json.dumps(value, separators=(",", ":"))
    return str(value) if value is not None else "null"


def _classify(prop: str) -> tuple[Severity, DriftStatus, DriftCategory, str]:
    """
    Return (severity, status, category, reason) for a given property name.

    Lookup order:
      1. Runtime table  → RUNTIME_STATE_CHANGE
      2. Dependency table → DEPENDENCY_CHANGE
      3. Configuration table → CONFIGURATION_DRIFT
      4. Fallback → CONFIGURATION_DRIFT / MEDIUM
    """
    if prop in _RUNTIME_PROPERTIES:
        return (
            Severity.LOW,
            DriftStatus.RUNTIME_CHANGE,
            DriftCategory.RUNTIME_STATE_CHANGE,
            _RUNTIME_PROPERTIES[prop],
        )

    if prop in _DEPENDENCY_PROPERTIES:
        return (
            Severity.LOW,
            DriftStatus.DEPENDENCY_CHANGE,
            DriftCategory.DEPENDENCY_CHANGE,
            _DEPENDENCY_PROPERTIES[prop],
        )

    if prop in _CONFIGURATION_PROPERTIES:
        severity, reason = _CONFIGURATION_PROPERTIES[prop]
        return (
            severity,
            DriftStatus.DRIFTED,
            DriftCategory.CONFIGURATION_DRIFT,
            reason,
        )

    # Fallback: treat any unknown property as a medium-severity config drift
    return (
        Severity.MEDIUM,
        DriftStatus.DRIFTED,
        DriftCategory.CONFIGURATION_DRIFT,
        f"The '{prop}' attribute differs from the Terraform desired state.",
    )


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def _extract_drifts_from_resource(resource: dict) -> list[DriftRecord]:
    """
    Compare change.before (desired) vs change.after (actual) for a single
    drifted resource and return one DriftRecord per differing attribute.
    """
    address: str = resource.get("address", "unknown")
    rtype: str = resource.get("type", "unknown")
    change: dict = resource.get("change", {})

    before: dict = change.get("before") or {}
    after: dict = change.get("after") or {}

    all_keys = set(before.keys()) | set(after.keys())
    records: list[DriftRecord] = []

    for key in sorted(all_keys):
        desired = before.get(key)
        actual = after.get(key)

        if desired == actual:
            continue

        severity, status, category, reason = _classify(key)

        records.append(
            DriftRecord(
                resource_name=address,
                resource_type=rtype,
                property=key,
                desired_value=_safe_str(desired),
                actual_value=_safe_str(actual),
                severity=severity,
                status=status,
                category=category,
                reason=reason,
            )
        )

    if records:
        cfg = sum(1 for r in records if r.category == DriftCategory.CONFIGURATION_DRIFT)
        rnt = sum(1 for r in records if r.category == DriftCategory.RUNTIME_STATE_CHANGE)
        dep = sum(1 for r in records if r.category == DriftCategory.DEPENDENCY_CHANGE)
        logger.info(
            "Drift on %s: %d config, %d runtime, %d dependency.",
            address, cfg, rnt, dep,
        )

    return records


def analyse_plan(plan_json: dict) -> list[DriftRecord]:
    """
    Entry point — analyse a full Terraform plan JSON dict and return all
    drift records found across every drifted resource.

    Args:
        plan_json: Parsed output of `terraform show -json <planfile>`.

    Returns:
        list[DriftRecord]: Every attribute-level drift found, classified by
        category (CONFIGURATION_DRIFT / RUNTIME_STATE_CHANGE / DEPENDENCY_CHANGE).
    """
    resource_drifts: list[dict] = plan_json.get("resource_drift", [])

    if not resource_drifts:
        logger.info("No resource drift entries found in plan output.")
        return []

    all_records: list[DriftRecord] = []
    for resource in resource_drifts:
        all_records.extend(_extract_drifts_from_resource(resource))

    cfg_count = sum(
        1 for r in all_records if r.category == DriftCategory.CONFIGURATION_DRIFT
    )
    rnt_count = sum(
        1 for r in all_records if r.category == DriftCategory.RUNTIME_STATE_CHANGE
    )
    dep_count = sum(
        1 for r in all_records if r.category == DriftCategory.DEPENDENCY_CHANGE
    )
    logger.info(
        "Drift engine complete: %d total (%d config / %d runtime / %d dependency).",
        len(all_records), cfg_count, rnt_count, dep_count,
    )

    return all_records
