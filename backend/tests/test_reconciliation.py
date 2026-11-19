"""
tests/test_reconciliation.py

Comprehensive tests for Safe Reconciliation Phase 1:
- Successful plan generation & parsing
- Resource action classification (CREATE, UPDATE, DELETE, REPLACE, NO_OP)
- Destructive change detection (DELETE, REPLACE)
- Sensitive attribute masking
- Retrieval by plan_id (and 404 for missing IDs)
- Concurrency lock protection (409 Conflict)
- Error handling for Terraform failures
- Strict verification that `apply` and `destroy` commands are prohibited
- PostgreSQL/SQLite persistence and recovery
"""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import repository, session
from app.db.models import Base
from app.main import (
    approve_reconciliation_plan_endpoint,
    create_reconciliation_plan_endpoint,
    get_drift,
    get_execution_readiness_endpoint,
    get_latest_reconciliation_plan_endpoint,
    get_reconciliation_plan_by_id_endpoint,
    reject_reconciliation_plan_endpoint,
)
from app.models.reconciliation import (
    PlanApprovalRequest,
    PlanRejectionRequest,
    PlanStatus,
    ReconciliationAction,
    ReconciliationPlanResponse,
)
from app.services import reconciliation_service, terraform_service
from app.services.terraform_service import TerraformConcurrencyError, TerraformError


@pytest.fixture
def sqlite_test_db():
    """Sets up an in-memory SQLite database for isolated database tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session.init_db(engine_override=engine)
    yield engine
    session.reset_db_state()


def _sample_plan_json(actions=["update"], before_type="t3.micro", after_type="t3.small"):
    """Helper to mock a Terraform show -json plan output."""
    return {
        "format_version": "1.2",
        "terraform_version": "1.5.0",
        "resource_changes": [
            {
                "address": "aws_instance.drift_demo",
                "type": "aws_instance",
                "name": "drift_demo",
                "change": {
                    "actions": actions,
                    "before": {
                        "ami": "ami-0c55b159cbfafe1f0",
                        "instance_type": before_type,
                        "key_name": "my-key",
                        "password_data": "supersecretpassword",
                    },
                    "after": {
                        "ami": "ami-0c55b159cbfafe1f0",
                        "instance_type": after_type,
                        "key_name": "my-key",
                        "password_data": "supersecretpassword",
                    },
                    "before_sensitive": {
                        "password_data": True,
                    },
                    "after_sensitive": {
                        "password_data": True,
                    },
                },
            }
        ],
    }


# ---------------------------------------------------------------------------
# 1. Action Classification Tests
# ---------------------------------------------------------------------------

def test_action_classification():
    """Verify standard Terraform action lists are correctly classified."""
    assert reconciliation_service._classify_action(["create"]) == ReconciliationAction.CREATE
    assert reconciliation_service._classify_action(["update"]) == ReconciliationAction.UPDATE
    assert reconciliation_service._classify_action(["delete"]) == ReconciliationAction.DELETE
    assert reconciliation_service._classify_action(["delete", "create"]) == ReconciliationAction.REPLACE
    assert reconciliation_service._classify_action(["create", "delete"]) == ReconciliationAction.REPLACE
    assert reconciliation_service._classify_action(["no-op"]) == ReconciliationAction.NO_OP
    assert reconciliation_service._classify_action(["read"]) == ReconciliationAction.NO_OP
    assert reconciliation_service._classify_action([]) == ReconciliationAction.NO_OP


# ---------------------------------------------------------------------------
# 2. Parsing & Destructive Change Detection
# ---------------------------------------------------------------------------

def test_parse_update_plan():
    """An update plan (e.g. t3.micro -> t3.small) is non-destructive."""
    plan_id = uuid.uuid4()
    raw = _sample_plan_json(actions=["update"])
    res = reconciliation_service.parse_terraform_plan_json(raw, plan_id=plan_id)

    assert res.plan_id == plan_id
    assert res.summary.update_count == 1
    assert res.summary.create_count == 0
    assert res.summary.delete_count == 0
    assert res.summary.replace_count == 0
    assert res.summary.total_changes == 1
    assert res.summary.has_destructive_changes is False
    assert len(res.warnings) == 0

    rc = res.resource_changes[0]
    assert rc.address == "aws_instance.drift_demo"
    assert rc.action == ReconciliationAction.UPDATE
    assert rc.is_destructive is False
    assert any(ca.property == "instance_type" and ca.before == "t3.micro" and ca.after == "t3.small" for ca in rc.changed_attributes)


def test_parse_replace_plan_is_destructive():
    """A replacement plan (["delete", "create"]) must be flagged as destructive."""
    plan_id = uuid.uuid4()
    raw = _sample_plan_json(actions=["delete", "create"])
    res = reconciliation_service.parse_terraform_plan_json(raw, plan_id=plan_id)

    assert res.summary.replace_count == 1
    assert res.summary.has_destructive_changes is True
    assert len(res.warnings) > 0
    assert "destructive" in res.warnings[0].lower()

    rc = res.resource_changes[0]
    assert rc.action == ReconciliationAction.REPLACE
    assert rc.is_destructive is True


def test_parse_delete_plan_is_destructive():
    """A delete plan (["delete"]) must be flagged as destructive."""
    plan_id = uuid.uuid4()
    raw = _sample_plan_json(actions=["delete"])
    res = reconciliation_service.parse_terraform_plan_json(raw, plan_id=plan_id)

    assert res.summary.delete_count == 1
    assert res.summary.has_destructive_changes is True
    rc = res.resource_changes[0]
    assert rc.action == ReconciliationAction.DELETE
    assert rc.is_destructive is True


# ---------------------------------------------------------------------------
# 3. Sensitive Value Masking
# ---------------------------------------------------------------------------

def test_sensitive_attributes_are_masked():
    """Sensitive attributes (like password_data, secret, token) must be masked."""
    plan_id = uuid.uuid4()
    raw = _sample_plan_json(actions=["update"])
    # Modify password in after to trigger changed_attribute
    raw["resource_changes"][0]["change"]["after"]["password_data"] = "newpassword"

    res = reconciliation_service.parse_terraform_plan_json(raw, plan_id=plan_id)
    rc = res.resource_changes[0]

    pwd_attr = next(ca for ca in rc.changed_attributes if ca.property == "password_data")
    assert pwd_attr.is_sensitive is True
    assert pwd_attr.before == "(sensitive value)"
    assert pwd_attr.after == "(sensitive value)"


# ---------------------------------------------------------------------------
# 4. Strict Safety Guard: Apply & Destroy Are Prohibited
# ---------------------------------------------------------------------------

def test_terraform_service_strictly_blocks_apply_and_destroy():
    """Verify _run raises ValueError if 'apply' or 'destroy' is attempted."""
    dummy_dir = Path(".")
    with pytest.raises(ValueError) as exc_apply:
        terraform_service._run(["apply", "-auto-approve"], cwd=dummy_dir)
    assert "strictly prohibited" in str(exc_apply.value).lower()

    with pytest.raises(ValueError) as exc_destroy:
        terraform_service._run(["destroy", "-auto-approve"], cwd=dummy_dir)
    assert "strictly prohibited" in str(exc_destroy.value).lower()


# ---------------------------------------------------------------------------
# 5. Concurrency Lock Protection
# ---------------------------------------------------------------------------

def test_concurrency_lock_raises_409():
    """When a Terraform operation is already in progress, new requests must be rejected with 409."""
    with terraform_service.acquire_terraform_lock():
        with pytest.raises(HTTPException) as exc_info:
            create_reconciliation_plan_endpoint()
        assert exc_info.value.status_code == 409
        assert "in progress" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# 6. Endpoint Tests: Generation & Retrieval
# ---------------------------------------------------------------------------

@patch("app.services.terraform_service.generate_reconciliation_plan_raw")
def test_create_and_get_plan_endpoint(mock_raw, sqlite_test_db):
    """POST /api/reconciliation/plan creates a plan, and GET retrieves it."""
    sample_raw = _sample_plan_json(actions=["update"])
    mock_raw.return_value = (sample_raw, Path("/tmp/plans/fake.tfplan"))

    # 1. Create plan
    created = create_reconciliation_plan_endpoint()
    assert created.plan_id is not None
    assert created.status == PlanStatus.PENDING_REVIEW
    assert created.summary.update_count == 1

    # 2. Get plan by ID
    fetched = get_reconciliation_plan_by_id_endpoint(plan_id=created.plan_id)
    assert fetched.plan_id == created.plan_id
    assert fetched.summary.update_count == 1
    assert len(fetched.resource_changes) == 1

    # 3. Get latest plan
    latest = get_latest_reconciliation_plan_endpoint()
    assert latest.plan_id == created.plan_id


def test_get_nonexistent_plan_returns_404(sqlite_test_db):
    """GET /api/reconciliation/plan/{id} returns 404 for unknown plan UUID."""
    random_id = uuid.uuid4()
    with pytest.raises(HTTPException) as exc_info:
        get_reconciliation_plan_by_id_endpoint(plan_id=random_id)
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


@patch("app.services.terraform_service.generate_reconciliation_plan_raw")
def test_terraform_error_returns_500(mock_raw):
    """If Terraform fails during plan generation, returns 500."""
    mock_raw.side_effect = TerraformError("Provider error: connection refused")
    with pytest.raises(HTTPException) as exc_info:
        create_reconciliation_plan_endpoint()
    assert exc_info.value.status_code == 500
    assert "failed" in exc_info.value.detail.lower()


def test_get_drift_returns_409_when_locked():
    """GET /api/drift returns 409 Conflict if another Terraform operation is in progress."""
    with terraform_service.acquire_terraform_lock():
        with pytest.raises(HTTPException) as exc_info:
            get_drift()
        assert exc_info.value.status_code == 409
        assert "in progress" in exc_info.value.detail.lower()


def test_lock_released_on_error():
    """Verify that if an error occurs inside acquire_terraform_lock, the lock is released."""
    try:
        with terraform_service.acquire_terraform_lock():
            raise RuntimeError("Unexpected failure during plan")
    except RuntimeError:
        pass

    # The lock must be available immediately
    assert not terraform_service._terraform_lock.locked()
    with terraform_service.acquire_terraform_lock():
        pass


def test_recursive_sensitive_masking_nested_dict_and_list():
    """Verify nested dictionary and list sensitive attributes are recursively sanitized."""
    plan_id = uuid.uuid4()
    raw = {
        "format_version": "1.2",
        "resource_changes": [
            {
                "address": "aws_db_instance.main",
                "type": "aws_db_instance",
                "change": {
                    "actions": ["update"],
                    "before": {
                        "db_name": "production",
                        "credentials": {
                            "username": "admin",
                            "master_password": "supersecretpassword1",
                        },
                        "auth_tokens": ["token-abc-123", "token-xyz-456"],
                    },
                    "after": {
                        "db_name": "production",
                        "credentials": {
                            "username": "admin",
                            "master_password": "supersecretpassword2",
                        },
                        "auth_tokens": ["token-abc-789", "token-xyz-456"],
                    },
                    "before_sensitive": {
                        "credentials": {
                            "master_password": True,
                        },
                        "auth_tokens": [True, False],
                    },
                    "after_sensitive": {
                        "credentials": {
                            "master_password": True,
                        },
                        "auth_tokens": [True, False],
                    },
                },
            }
        ],
    }

    res = reconciliation_service.parse_terraform_plan_json(raw, plan_id=plan_id)
    rc = res.resource_changes[0]

    # Verify sanitized before and after dictionaries do not contain secret passwords
    assert rc.before["credentials"]["master_password"] == "(sensitive value)"
    assert rc.after["credentials"]["master_password"] == "(sensitive value)"
    assert rc.before["auth_tokens"][0] == "(sensitive value)"
    assert rc.after["auth_tokens"][0] == "(sensitive value)"

    # Verify change description does NOT contain the raw password or token
    assert "supersecretpassword" not in rc.change_description
    assert "token-abc" not in rc.change_description


def test_non_whitelisted_commands_blocked():
    """Verify any command not in ALLOWED_SUBCOMMANDS (plan, show, version) is blocked."""
    dummy_dir = Path(".")
    for prohibited in ["apply", "destroy", "taint", "untaint", "import", "push", "refresh"]:
        with pytest.raises(ValueError) as exc:
            terraform_service._run([prohibited], cwd=dummy_dir)
        assert "strictly prohibited" in str(exc.value).lower()


def test_missing_tfplan_binary_adds_warning(sqlite_test_db):
    """When a plan is fetched but its .tfplan file is missing from disk, a warning is included."""
    fake_id = uuid.uuid4()
    # Save a plan record in DB pointing to a non-existent file
    with session.get_db_session() as db:
        rep = reconciliation_service.parse_terraform_plan_json(
            _sample_plan_json(actions=["update"]),
            plan_id=fake_id,
        )
        repository.save_reconciliation_plan(db, rep, plan_path="/nonexistent/plans/missing.tfplan")

    fetched = get_reconciliation_plan_by_id_endpoint(plan_id=fake_id)
    assert any("missing" in w.lower() or "not present" in w.lower() for w in fetched.warnings)


# ---------------------------------------------------------------------------
# 7. Phase 2A Approval Workflow Tests
# ---------------------------------------------------------------------------

@patch("app.services.terraform_service.generate_reconciliation_plan_raw")
def test_successful_plan_approval(mock_raw, sqlite_test_db, tmp_path):
    """Approve a PENDING_REVIEW plan: status becomes APPROVED and audit fields recorded."""
    plan_file = tmp_path / "plan_success.tfplan"
    plan_file.write_bytes(b"binary terraform plan contents")
    mock_raw.return_value = (_sample_plan_json(actions=["update"]), plan_file)

    created = create_reconciliation_plan_endpoint()
    assert created.status == PlanStatus.PENDING_REVIEW

    # Approve
    req = PlanApprovalRequest(approved_by="devops_lead", comment="Verified safe instance_type update")
    approved = approve_reconciliation_plan_endpoint(plan_id=created.plan_id, request=req)

    assert approved.status == PlanStatus.APPROVED
    assert approved.approved_by == "devops_lead"
    assert approved.approved_at is not None
    assert approved.approval_comment == "Verified safe instance_type update"

    # Verify retrieved plan retains approval in DB
    refetched = get_reconciliation_plan_by_id_endpoint(plan_id=created.plan_id)
    assert refetched.status == PlanStatus.APPROVED
    assert refetched.approved_by == "devops_lead"


@patch("app.services.terraform_service.generate_reconciliation_plan_raw")
def test_repeated_approval_fails(mock_raw, sqlite_test_db, tmp_path):
    """Approving an already APPROVED plan raises HTTP 400."""
    plan_file = tmp_path / "plan_repeat.tfplan"
    plan_file.write_bytes(b"binary terraform plan contents")
    mock_raw.return_value = (_sample_plan_json(actions=["update"]), plan_file)

    created = create_reconciliation_plan_endpoint()
    req = PlanApprovalRequest(approved_by="first_approver")
    approve_reconciliation_plan_endpoint(plan_id=created.plan_id, request=req)

    # Second approval attempt
    with pytest.raises(HTTPException) as exc_info:
        approve_reconciliation_plan_endpoint(plan_id=created.plan_id, request=req)
    assert exc_info.value.status_code == 400
    assert "already" in exc_info.value.detail.lower() and "approved" in exc_info.value.detail.lower()


def test_approve_nonexistent_plan_returns_404(sqlite_test_db):
    """Approving a non-existent plan ID returns 404."""
    random_id = uuid.uuid4()
    req = PlanApprovalRequest(approved_by="admin")
    with pytest.raises(HTTPException) as exc_info:
        approve_reconciliation_plan_endpoint(plan_id=random_id, request=req)
    assert exc_info.value.status_code == 404


@patch("app.services.terraform_service.generate_reconciliation_plan_raw")
def test_approval_fails_if_plan_file_missing(mock_raw, sqlite_test_db, tmp_path):
    """Approving a plan whose .tfplan file was removed from disk raises 400."""
    plan_file = tmp_path / "plan_missing.tfplan"
    plan_file.write_bytes(b"temp plan")
    mock_raw.return_value = (_sample_plan_json(actions=["update"]), plan_file)

    created = create_reconciliation_plan_endpoint()

    # Delete the binary plan file to simulate loss
    plan_file.unlink()

    req = PlanApprovalRequest(approved_by="admin")
    with pytest.raises(HTTPException) as exc_info:
        approve_reconciliation_plan_endpoint(plan_id=created.plan_id, request=req)
    assert exc_info.value.status_code == 400
    assert "missing" in exc_info.value.detail.lower()


@patch("app.services.terraform_service.generate_reconciliation_plan_raw")
def test_approval_fails_if_plan_hash_corrupted(mock_raw, sqlite_test_db, tmp_path):
    """Approving a plan whose .tfplan file was tampered with raises 400."""
    plan_file = tmp_path / "plan_corrupt.tfplan"
    plan_file.write_bytes(b"original binary plan")
    mock_raw.return_value = (_sample_plan_json(actions=["update"]), plan_file)

    created = create_reconciliation_plan_endpoint()

    # Tamper with the binary plan file
    plan_file.write_bytes(b"tampered or replaced binary plan")

    req = PlanApprovalRequest(approved_by="admin")
    with pytest.raises(HTTPException) as exc_info:
        approve_reconciliation_plan_endpoint(plan_id=created.plan_id, request=req)
    assert exc_info.value.status_code == 400
    assert "mismatch" in exc_info.value.detail.lower() or "integrity" in exc_info.value.detail.lower()


@patch("app.services.terraform_service.generate_reconciliation_plan_raw")
def test_approval_fails_if_plan_expired(mock_raw, sqlite_test_db, tmp_path):
    """Approving a plan whose TTL window expired raises 400."""
    from datetime import timedelta
    plan_file = tmp_path / "plan_expired.tfplan"
    plan_file.write_bytes(b"binary plan")
    mock_raw.return_value = (_sample_plan_json(actions=["update"]), plan_file)

    created = create_reconciliation_plan_endpoint()

    # Force expiration by setting expires_at in the past
    with session.get_db_session() as db:
        record = repository.get_reconciliation_plan_by_id(db, created.plan_id)
        if record:
            record.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
            db.commit()

    cached = reconciliation_service.get_cached_plan_by_id(created.plan_id)
    if cached:
        cached.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)

    req = PlanApprovalRequest(approved_by="admin")
    with pytest.raises(HTTPException) as exc_info:
        approve_reconciliation_plan_endpoint(plan_id=created.plan_id, request=req)
    assert exc_info.value.status_code == 400
    assert "expired" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# 8. Phase 2A Rejection Workflow Tests
# ---------------------------------------------------------------------------

@patch("app.services.terraform_service.generate_reconciliation_plan_raw")
def test_successful_plan_rejection(mock_raw, sqlite_test_db, tmp_path):
    """Rejecting a plan sets status to REJECTED and records reason."""
    plan_file = tmp_path / "plan_reject.tfplan"
    plan_file.write_bytes(b"plan bytes")
    mock_raw.return_value = (_sample_plan_json(actions=["update"]), plan_file)

    created = create_reconciliation_plan_endpoint()
    req = PlanRejectionRequest(rejected_by="secops", reason="Instance type modification not approved for sprint 12")

    rejected = reject_reconciliation_plan_endpoint(plan_id=created.plan_id, request=req)
    assert rejected.status == PlanStatus.REJECTED
    assert rejected.rejected_by == "secops"
    assert rejected.rejection_reason == "Instance type modification not approved for sprint 12"
    assert rejected.rejected_at is not None

    # Cannot approve a rejected plan
    app_req = PlanApprovalRequest(approved_by="admin")
    with pytest.raises(HTTPException) as exc_info:
        approve_reconciliation_plan_endpoint(plan_id=created.plan_id, request=app_req)
    assert exc_info.value.status_code == 400
    assert "rejected" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# 9. Execution Readiness Inspection Tests
# ---------------------------------------------------------------------------

@patch("app.services.terraform_service.generate_reconciliation_plan_raw")
def test_execution_readiness_on_approved_plan(mock_raw, sqlite_test_db, tmp_path):
    """An approved plan with intact binary is ready for execution, with execution blocked by design."""
    plan_file = tmp_path / "plan_ready.tfplan"
    plan_file.write_bytes(b"valid plan bytes")
    mock_raw.return_value = (_sample_plan_json(actions=["update"]), plan_file)

    created = create_reconciliation_plan_endpoint()
    approve_reconciliation_plan_endpoint(
        plan_id=created.plan_id,
        request=PlanApprovalRequest(approved_by="admin"),
    )

    readiness = get_execution_readiness_endpoint(plan_id=created.plan_id)
    assert readiness.is_ready is True
    assert readiness.status == PlanStatus.APPROVED
    assert len(readiness.ineligibility_reasons) == 0
    assert "locked" in readiness.execution_blocked_reason.lower() or "blocked" in readiness.execution_blocked_reason.lower()
    assert all(c.passed for c in readiness.checks)


@patch("app.services.terraform_service.generate_reconciliation_plan_raw")
def test_execution_readiness_fails_when_not_approved(mock_raw, sqlite_test_db, tmp_path):
    """A PENDING_REVIEW plan is not ready for execution."""
    plan_file = tmp_path / "plan_unapproved.tfplan"
    plan_file.write_bytes(b"valid plan bytes")
    mock_raw.return_value = (_sample_plan_json(actions=["update"]), plan_file)

    created = create_reconciliation_plan_endpoint()
    readiness = get_execution_readiness_endpoint(plan_id=created.plan_id)

    assert readiness.is_ready is False
    assert readiness.status == PlanStatus.PENDING_REVIEW
    assert any("approved" in r.lower() for r in readiness.ineligibility_reasons)

