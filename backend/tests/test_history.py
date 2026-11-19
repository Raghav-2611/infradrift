"""
tests/test_history.py

Comprehensive tests for PostgreSQL / SQLite drift scan history:
- Saving scans and calculating severity counts
- Retrieving paginated history (order, limit, offset)
- Retrieving individual scan details
- UUID and pagination parameter handling
- Handling missing database configuration (graceful degradation)
- Database failures not breaking live drift detection
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.db import repository, session
from app.db.models import Base
from app.main import (
    get_drift,
    get_history,
    get_history_detail,
    health_check,
    liveness_check,
    readiness_check,
)
from app.models.drift import (
    DriftCategory,
    DriftRecord,
    DriftReport,
    DriftStatus,
    ReportStatus,
    Severity,
)


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


def _make_sample_report(drift_count: int = 3) -> DriftReport:
    """Helper to generate a valid DriftReport with mixed severities."""
    drifts = [
        DriftRecord(
            resource_name="aws_instance.web",
            resource_type="aws_instance",
            property="instance_type",
            desired_value="t3.small",
            actual_value="t3.micro",
            severity=Severity.HIGH,
            status=DriftStatus.DRIFTED,
            category=DriftCategory.CONFIGURATION_DRIFT,
            reason="EC2 instance type differs from desired.",
        ),
        DriftRecord(
            resource_name="aws_instance.web",
            resource_type="aws_instance",
            property="private_ip",
            desired_value="10.0.1.50",
            actual_value="10.0.1.55",
            severity=Severity.MEDIUM,
            status=DriftStatus.DRIFTED,
            category=DriftCategory.CONFIGURATION_DRIFT,
            reason="Private IP address differs.",
        ),
        DriftRecord(
            resource_name="aws_instance.web",
            resource_type="aws_instance",
            property="public_ip",
            desired_value="54.221.48.228",
            actual_value="50.19.42.29",
            severity=Severity.LOW,
            status=DriftStatus.RUNTIME_CHANGE,
            category=DriftCategory.RUNTIME_STATE_CHANGE,
            reason="The EC2 instance received a different public address.",
        ),
    ][:drift_count]

    return DriftReport(
        total_drifts=len(drifts),
        configuration_drifts=sum(1 for d in drifts if d.category == DriftCategory.CONFIGURATION_DRIFT),
        runtime_changes=sum(1 for d in drifts if d.category == DriftCategory.RUNTIME_STATE_CHANGE),
        status=ReportStatus.DRIFT_DETECTED if drifts else ReportStatus.NO_DRIFT,
        drifts=drifts,
    )


# ---------------------------------------------------------------------------
# 1. Repository Tests: Saving & Severity Counting
# ---------------------------------------------------------------------------

def test_save_drift_scan_and_severity_counts(sqlite_test_db):
    """Test saving a scan snapshot and verifying correct severity calculation."""
    report = _make_sample_report(3)

    with session.get_db_session() as db:
        saved = repository.save_drift_scan(db, report)
        assert saved is not None
        assert isinstance(saved.id, uuid.UUID)
        assert saved.total_drifts == 3
        assert saved.configuration_drifts == 2
        assert saved.runtime_changes == 1
        assert saved.high_severity == 1
        assert saved.medium_severity == 1
        assert saved.low_severity == 1
        assert len(saved.drifts) == 3


def test_save_empty_drifts_scan(sqlite_test_db):
    """Test saving a scan with 0 drifts (100% in sync)."""
    report = DriftReport(
        total_drifts=0,
        configuration_drifts=0,
        runtime_changes=0,
        status=ReportStatus.NO_DRIFT,
        drifts=[],
    )

    with session.get_db_session() as db:
        saved = repository.save_drift_scan(db, report)
        assert saved is not None
        assert saved.total_drifts == 0
        assert saved.high_severity == 0
        assert saved.medium_severity == 0
        assert saved.low_severity == 0
        assert saved.status == "NO_DRIFT"


# ---------------------------------------------------------------------------
# 2. History API: Listing & Pagination
# ---------------------------------------------------------------------------

def test_get_history_empty_list(sqlite_test_db):
    """get_history returns empty list when no scans have been recorded."""
    res = get_history(limit=20, offset=0)
    assert res.total_scans == 0
    assert res.limit == 20
    assert res.offset == 0
    assert res.scans == []


def test_get_history_paginated_ordering(sqlite_test_db):
    """get_history returns scans newest first and honors limit and offset."""
    with session.get_db_session() as db:
        for i in range(5):
            rep = _make_sample_report(i % 3 + 1)
            repository.save_drift_scan(db, rep)

    # First page: limit 2, offset 0
    page1 = get_history(limit=2, offset=0)
    assert page1.total_scans == 5
    assert len(page1.scans) == 2

    # Second page: limit 2, offset 2
    page2 = get_history(limit=2, offset=2)
    assert page2.total_scans == 5
    assert len(page2.scans) == 2

    # Verify descending ordering by scanned_at
    assert page1.scans[0].scanned_at >= page1.scans[1].scanned_at
    assert page1.scans[1].scanned_at >= page2.scans[0].scanned_at

    # Verify distinct scans across pages
    ids_page1 = [s.id for s in page1.scans]
    ids_page2 = [s.id for s in page2.scans]
    assert set(ids_page1).isdisjoint(set(ids_page2))


# ---------------------------------------------------------------------------
# 3. History Detail API: GET /api/history/{scan_id}
# ---------------------------------------------------------------------------

def test_get_history_detail_success(sqlite_test_db):
    """get_history_detail returns full scan details with original drift records."""
    report = _make_sample_report(3)
    with session.get_db_session() as db:
        saved = repository.save_drift_scan(db, report)
        scan_id = saved.id

    detail = get_history_detail(scan_id=scan_id)
    assert detail.id == scan_id
    assert detail.total_drifts == 3
    assert detail.high_severity == 1
    assert len(detail.drifts) == 3
    assert detail.drifts[0].resource_name == "aws_instance.web"
    assert detail.drifts[0].property == "instance_type"


def test_get_history_detail_not_found(sqlite_test_db):
    """get_history_detail raises 404 HTTPException when scan ID does not exist."""
    random_id = uuid.uuid4()
    with pytest.raises(HTTPException) as exc_info:
        get_history_detail(scan_id=random_id)
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# 4. Missing Database Configuration (Graceful Degradation)
# ---------------------------------------------------------------------------

def test_history_endpoints_when_db_disabled():
    """When DATABASE_URL is not set, history endpoints return 503 and health reports disconnected."""
    session.reset_db_state()

    # Health still returns ok with database_connected = False
    health = health_check()
    assert health["status"] == "ok"
    assert health["database_connected"] is False

    # List endpoint raises 503
    with pytest.raises(HTTPException) as exc_info:
        get_history(limit=20, offset=0)
    assert exc_info.value.status_code == 503
    assert "disabled" in exc_info.value.detail.lower()

    # Detail endpoint raises 503
    with pytest.raises(HTTPException) as exc_info2:
        get_history_detail(scan_id=uuid.uuid4())
    assert exc_info2.value.status_code == 503


# ---------------------------------------------------------------------------
# 5. Database Failure Must Not Break Live Drift Detection
# ---------------------------------------------------------------------------

@patch("app.services.terraform_service.get_refresh_plan")
def test_db_failure_does_not_break_get_drift(mock_plan, sqlite_test_db):
    """If database persistence raises an error, get_drift still returns the live drift report."""
    mock_plan.return_value = {
        "resource_drift": [
            {
                "address": "aws_instance.drift_demo",
                "type": "aws_instance",
                "change": {
                    "before": {"instance_type": "t3.small"},
                    "after": {"instance_type": "t3.micro"},
                },
            }
        ]
    }

    # Force repository.save_drift_scan to raise an unexpected database exception
    with patch("app.db.repository.save_drift_scan", side_effect=Exception("Database connection timeout")):
        report = get_drift()

    # The drift scan must still succeed and return the report
    assert report.total_drifts == 1
    assert report.configuration_drifts == 1
    assert report.status == ReportStatus.DRIFT_DETECTED
    assert report.drifts[0].property == "instance_type"
    # scan_id remains None since database save failed
    assert report.scan_id is None


@patch("app.services.terraform_service.get_refresh_plan")
def test_successful_get_drift_persists_scan(mock_plan, sqlite_test_db):
    """Successful get_drift attaches scan_id and scanned_at when database is connected."""
    mock_plan.return_value = {
        "resource_drift": [
            {
                "address": "aws_instance.drift_demo",
                "type": "aws_instance",
                "change": {
                    "before": {"instance_type": "t3.small"},
                    "after": {"instance_type": "t3.micro"},
                },
            }
        ]
    }

    report = get_drift()

    # Scan ID and timestamp should be populated
    assert report.scan_id is not None
    assert report.scanned_at is not None
    assert isinstance(report.scan_id, uuid.UUID)

    # Verify that the scan can now be retrieved via history
    detail = get_history_detail(scan_id=report.scan_id)
    assert detail.id == report.scan_id
    assert detail.total_drifts == 1
    assert detail.drifts[0].property == "instance_type"


def test_liveness_endpoint():
    """Verify GET /health/live returns 200 alive status."""
    res = liveness_check()
    assert res["status"] == "alive"
    assert res["service"] == "infradrift-backend"


def test_readiness_endpoint_with_and_without_db(sqlite_test_db):
    """Verify GET /health/ready returns 200 ready when DB is healthy and when DB is disabled."""
    # With DB enabled:
    res = readiness_check()
    assert res["status"] == "ready"
    assert res["database_configured"] is True
    assert res["database_connected"] is True

    # With DB disabled:
    session.reset_db_state()
    res2 = readiness_check()
    assert res2["status"] == "ready"
    assert res2["database_configured"] is False
    assert res2["database_connected"] is None


def test_load_runtime_env_and_url_normalization(tmp_path, monkeypatch):
    """Verify runtime env loading handles unquoted, quoted, and export formats, and normalizes properly."""
    # Ensure DATABASE_URL is not set
    monkeypatch.delenv("DATABASE_URL", raising=False)

    env_file = tmp_path / ".env.runtime"
    env_file.write_text(
        '# Sample runtime env\n'
        'export TEST_PORT=8000\n'
        'DATABASE_URL="postgresql+psycopg://infradrift_user:secret_pass@127.0.0.1:5432/infradrift"\n'
        'OTHER_SETTING=\'test_val\'\n',
        encoding="utf-8",
    )

    # Patch candidates in session
    monkeypatch.setattr(
        "app.db.session.load_runtime_env",
        lambda: _mock_load_env(env_file),
    )

    def _mock_load_env(path):
        import os
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v

    _mock_load_env(env_file)
    import os
    assert os.environ.get("DATABASE_URL") == "postgresql+psycopg://infradrift_user:secret_pass@127.0.0.1:5432/infradrift"

    # Test URL normalization with quotes
    from app.db.session import normalize_database_url
    assert normalize_database_url('"postgresql://user:pass@localhost:5432/db"') == "postgresql+psycopg://user:pass@localhost:5432/db"
    assert normalize_database_url("'postgres://user:pass@localhost:5432/db'") == "postgresql+psycopg://user:pass@localhost:5432/db"


def test_sanitize_error_message_never_exposes_password():
    """Verify passwords are scrubbed from error messages."""
    from app.db.session import _sanitize_error_message

    msg = "Could not connect to postgresql+psycopg://infradrift_user:super_secret_pwd_123@127.0.0.1:5432/infradrift"
    sanitized = _sanitize_error_message(msg)
    assert "super_secret_pwd_123" not in sanitized
    assert "infradrift_user:***@" in sanitized

    msg2 = "FATAL: password=my_plain_pass failed for user infradrift"
    sanitized2 = _sanitize_error_message(msg2)
    assert "my_plain_pass" not in sanitized2
    assert "password=***" in sanitized2
