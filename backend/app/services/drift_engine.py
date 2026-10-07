"""
services/drift_engine.py

Analyses a Terraform refresh-only plan JSON and extracts every attribute
where the real AWS state differs from Terraform's desired/known state.

How a refresh-only plan encodes drift:
  plan["resource_drift"] → list of resources where live state ≠ last-known state.
  Each resource entry has:
    - "address"         → e.g. "aws_instance.drift_demo"
    - "type"            → e.g. "aws_instance"
    - "change.before"   → attributes Terraform has stored in state (desired)
    - "change.after"    → attributes freshly read from AWS (actual)

A drift exists for every key where before[key] != after[key].
"""

from __future__ import annotations

import logging
from typing import Any

from app.models.drift import DriftRecord, DriftStatus, Severity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity classification
# High-impact attributes get CRITICAL / HIGH; metadata gets LOW.
# ---------------------------------------------------------------------------

_HIGH_SEVERITY_PROPERTIES: set[str] = {
    "instance_type",
    "ami",
    "vpc_security_group_ids",
    "subnet_id",
    "iam_instance_profile",
    "root_block_device",
    "ebs_block_device",
}

_CRITICAL_SEVERITY_PROPERTIES: set[str] = {
    "deletion_protection",
    "disable_api_termination",
}

_LOW_SEVERITY_PROPERTIES: set[str] = {
    "tags",
    "tags_all",
    "volume_tags",
}


def _classify_severity(prop: str) -> Severity:
    if prop in _CRITICAL_SEVERITY_PROPERTIES:
        return Severity.CRITICAL
    if prop in _HIGH_SEVERITY_PROPERTIES:
        return Severity.HIGH
    if prop in _LOW_SEVERITY_PROPERTIES:
        return Severity.LOW
    return Severity.MEDIUM


def _safe_str(value: Any) -> str:
    """Convert any value to a compact, readable string."""
    if isinstance(value, (list, dict)):
        import json
        return json.dumps(value, separators=(",", ":"))
    return str(value) if value is not None else "null"


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
            continue  # no drift on this attribute

        records.append(
            DriftRecord(
                resource_name=address,
                resource_type=rtype,
                property=key,
                desired_value=_safe_str(desired),
                actual_value=_safe_str(actual),
                severity=_classify_severity(key),
                status=DriftStatus.DRIFTED,
            )
        )

    if records:
        logger.info(
            "Drift detected on %s: %d attribute(s) differ.", address, len(records)
        )

    return records


def analyse_plan(plan_json: dict) -> list[DriftRecord]:
    """
    Entry point — analyse a full Terraform plan JSON dict and return all
    drift records found across every drifted resource.

    Args:
        plan_json: Parsed output of `terraform show -json <planfile>`.

    Returns:
        list[DriftRecord]: Every attribute-level drift found.
    """
    resource_drifts: list[dict] = plan_json.get("resource_drift", [])

    if not resource_drifts:
        logger.info("No resource drift entries found in plan output.")
        return []

    all_records: list[DriftRecord] = []
    for resource in resource_drifts:
        all_records.extend(_extract_drifts_from_resource(resource))

    logger.info("Drift engine complete: %d drift record(s) found.", len(all_records))
    return all_records
