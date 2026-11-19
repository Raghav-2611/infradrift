"""
tests/test_drift_engine.py

Unit tests for drift_engine.py verifying:
1. Dynamic public IP and DNS changes are classified as RUNTIME_STATE_CHANGE (not configuration drift).
2. Changed IP/DNS values (both present and differ) explain that the instance received a different
   public address, potentially after a stop/start or replacement, without claiming values became empty.
3. Empty actual IP/DNS values (e.g. stopped instances) explain that values become empty when stopped.
4. Unchanged IP/DNS values generate no drift records.
5. Configuration drifts (e.g. instance_type) and dependency drifts (e.g. ebs_optimized) are preserved.
"""

import pytest
from app.models.drift import DriftCategory, DriftStatus, Severity
from app.services import drift_engine


# ---------------------------------------------------------------------------
# Tests for changed public IP and public DNS values (both present but differ)
# ---------------------------------------------------------------------------

def test_changed_public_ip_classified_as_runtime_state_change():
    """When old and new IP values are present and differ, must be RUNTIME_STATE_CHANGE."""
    record = drift_engine._classify("public_ip", desired="54.221.48.228", actual="50.19.42.29")
    severity, status, category, reason = record

    assert category == DriftCategory.RUNTIME_STATE_CHANGE
    assert status == DriftStatus.RUNTIME_CHANGE
    assert severity == Severity.LOW
    assert "received a different public address" in reason
    assert "stop/start or replacement" in reason
    assert "empty" not in reason.lower()


def test_changed_public_dns_classified_as_runtime_state_change():
    """When old and new DNS values are present and differ, must be RUNTIME_STATE_CHANGE."""
    record = drift_engine._classify(
        "public_dns",
        desired="ec2-54-221-48-228.compute-1.amazonaws.com",
        actual="ec2-50-19-42-29.compute-1.amazonaws.com",
    )
    severity, status, category, reason = record

    assert category == DriftCategory.RUNTIME_STATE_CHANGE
    assert status == DriftStatus.RUNTIME_CHANGE
    assert severity == Severity.LOW
    assert "received a different public address" in reason
    assert "stop/start or replacement" in reason
    assert "empty" not in reason.lower()


# ---------------------------------------------------------------------------
# Tests for empty actual values (e.g. instance stopped)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("empty_val", ["", None, "   "])
def test_empty_actual_public_ip_explains_stopped_instance(empty_val):
    """When actual public_ip is empty, it should explain that it becomes empty when stopped."""
    record = drift_engine._classify("public_ip", desired="54.221.48.228", actual=empty_val)
    severity, status, category, reason = record

    assert category == DriftCategory.RUNTIME_STATE_CHANGE
    assert status == DriftStatus.RUNTIME_CHANGE
    assert severity == Severity.LOW
    assert "becomes empty when the instance is stopped" in reason


@pytest.mark.parametrize("empty_val", ["", None, "   "])
def test_empty_actual_public_dns_explains_stopped_instance(empty_val):
    """When actual public_dns is empty, it should explain that it becomes empty when stopped."""
    record = drift_engine._classify(
        "public_dns",
        desired="ec2-54-221-48-228.compute-1.amazonaws.com",
        actual=empty_val,
    )
    severity, status, category, reason = record

    assert category == DriftCategory.RUNTIME_STATE_CHANGE
    assert status == DriftStatus.RUNTIME_CHANGE
    assert severity == Severity.LOW
    assert "becomes empty when the instance is stopped" in reason


# ---------------------------------------------------------------------------
# Tests for empty desired values (e.g. started/rebooted instance)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("empty_val", ["", None])
def test_empty_desired_public_ip_does_not_claim_empty(empty_val):
    """When desired was empty and actual is populated, must not claim value became empty."""
    record = drift_engine._classify("public_ip", desired=empty_val, actual="50.19.42.29")
    severity, status, category, reason = record

    assert category == DriftCategory.RUNTIME_STATE_CHANGE
    assert status == DriftStatus.RUNTIME_CHANGE
    assert severity == Severity.LOW
    assert "empty" not in reason.lower()


# ---------------------------------------------------------------------------
# Tests for unchanged public IP and DNS values
# ---------------------------------------------------------------------------

def test_unchanged_public_ip_and_dns_produce_no_drifts():
    """When desired == actual, no drift records should be generated."""
    resource = {
        "address": "aws_instance.drift_demo",
        "type": "aws_instance",
        "change": {
            "before": {
                "public_ip": "54.221.48.228",
                "public_dns": "ec2-54-221-48-228.compute-1.amazonaws.com",
            },
            "after": {
                "public_ip": "54.221.48.228",
                "public_dns": "ec2-54-221-48-228.compute-1.amazonaws.com",
            },
        },
    }
    records = drift_engine._extract_drifts_from_resource(resource)
    assert len(records) == 0


def test_both_empty_public_ip_produces_no_drifts():
    """When both desired and actual are empty/None, no drift is generated."""
    resource = {
        "address": "aws_instance.drift_demo",
        "type": "aws_instance",
        "change": {
            "before": {"public_ip": ""},
            "after": {"public_ip": ""},
        },
    }
    records = drift_engine._extract_drifts_from_resource(resource)
    assert len(records) == 0


# ---------------------------------------------------------------------------
# Tests for preservation of configuration and dependency drifts
# ---------------------------------------------------------------------------

def test_instance_type_is_high_configuration_drift():
    """Verify instance_type change remains HIGH severity CONFIGURATION_DRIFT."""
    severity, status, category, reason = drift_engine._classify("instance_type", desired="t3.small", actual="t3.micro")

    assert category == DriftCategory.CONFIGURATION_DRIFT
    assert status == DriftStatus.DRIFTED
    assert severity == Severity.HIGH
    assert "instance type differs" in reason.lower()


def test_ebs_optimized_is_low_dependency_change():
    """Verify ebs_optimized change remains LOW severity DEPENDENCY_CHANGE."""
    severity, status, category, reason = drift_engine._classify("ebs_optimized", desired=False, actual=True)

    assert category == DriftCategory.DEPENDENCY_CHANGE
    assert status == DriftStatus.DEPENDENCY_CHANGE
    assert severity == Severity.LOW
    assert "side-effect of the instance_type drift" in reason


# ---------------------------------------------------------------------------
# Full plan analysis test
# ---------------------------------------------------------------------------

def test_full_plan_analysis():
    """Verify analyse_plan end-to-end on a realistic plan JSON."""
    plan = {
        "resource_drift": [
            {
                "address": "aws_instance.drift_demo",
                "type": "aws_instance",
                "change": {
                    "before": {
                        "instance_type": "t3.small",
                        "ebs_optimized": False,
                        "public_ip": "54.221.48.228",
                        "public_dns": "ec2-54-221-48-228.compute-1.amazonaws.com",
                        "tags": {"Environment": "production"},
                    },
                    "after": {
                        "instance_type": "t3.micro",
                        "ebs_optimized": True,
                        "public_ip": "50.19.42.29",
                        "public_dns": "ec2-50-19-42-29.compute-1.amazonaws.com",
                        "tags": {"Environment": "production"},  # unchanged
                    },
                },
            }
        ]
    }

    records = drift_engine.analyse_plan(plan)
    assert len(records) == 4

    record_by_prop = {r.property: r for r in records}

    # 1. instance_type: CONFIGURATION_DRIFT, HIGH
    it = record_by_prop["instance_type"]
    assert it.category == DriftCategory.CONFIGURATION_DRIFT
    assert it.severity == Severity.HIGH
    assert it.desired_value == "t3.small"
    assert it.actual_value == "t3.micro"

    # 2. ebs_optimized: DEPENDENCY_CHANGE, LOW
    ebs = record_by_prop["ebs_optimized"]
    assert ebs.category == DriftCategory.DEPENDENCY_CHANGE
    assert ebs.severity == Severity.LOW

    # 3. public_ip: RUNTIME_STATE_CHANGE, LOW, explanation mentions different address, not empty
    pip = record_by_prop["public_ip"]
    assert pip.category == DriftCategory.RUNTIME_STATE_CHANGE
    assert pip.severity == Severity.LOW
    assert "received a different public address" in pip.reason
    assert "empty" not in pip.reason.lower()

    # 4. public_dns: RUNTIME_STATE_CHANGE, LOW, explanation mentions different address, not empty
    pdns = record_by_prop["public_dns"]
    assert pdns.category == DriftCategory.RUNTIME_STATE_CHANGE
    assert pdns.severity == Severity.LOW
    assert "received a different public address" in pdns.reason
    assert "empty" not in pdns.reason.lower()
