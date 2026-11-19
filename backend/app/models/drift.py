"""
models/drift.py
Pydantic models that describe infrastructure drift records,
top-level API responses, and persistent drift scan history.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DriftSource(str, Enum):
    AWS_TERRAFORM = "AWS_TERRAFORM"
    KUBERNETES_HELM = "KUBERNETES_HELM"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DriftStatus(str, Enum):
    DRIFTED = "DRIFTED"
    RUNTIME_CHANGE = "RUNTIME_CHANGE"
    DEPENDENCY_CHANGE = "DEPENDENCY_CHANGE"
    IN_SYNC = "IN_SYNC"


class DriftCategory(str, Enum):
    CONFIGURATION_DRIFT = "CONFIGURATION_DRIFT"
    RUNTIME_STATE_CHANGE = "RUNTIME_STATE_CHANGE"
    DEPENDENCY_CHANGE = "DEPENDENCY_CHANGE"


class ReportStatus(str, Enum):
    DRIFT_DETECTED = "DRIFT_DETECTED"
    NO_DRIFT = "NO_DRIFT"
    ERROR = "ERROR"


class DriftRecord(BaseModel):
    """A single attribute-level drift between desired and actual state."""

    model_config = ConfigDict(from_attributes=True)

    resource_name: str
    resource_type: str
    property: str
    desired_value: str
    actual_value: str
    severity: Severity
    status: DriftStatus
    category: DriftCategory
    reason: str
    source: DriftSource = DriftSource.AWS_TERRAFORM
    namespace: Optional[str] = None


class DriftReport(BaseModel):
    """Top-level response returned by GET /api/drift."""

    model_config = ConfigDict(from_attributes=True)

    total_drifts: int
    configuration_drifts: int
    runtime_changes: int
    status: ReportStatus
    drifts: list[DriftRecord]
    scan_id: Optional[UUID] = None
    scanned_at: Optional[datetime] = None


class DriftScanSummary(BaseModel):
    """Summary representation of a historical drift scan."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scanned_at: datetime
    status: ReportStatus
    total_drifts: int
    configuration_drifts: int
    runtime_changes: int
    high_severity: int
    medium_severity: int
    low_severity: int


class DriftHistoryResponse(BaseModel):
    """Paginated list response returned by GET /api/history."""

    total_scans: int
    limit: int
    offset: int
    scans: list[DriftScanSummary]


class DriftScanDetail(BaseModel):
    """Detailed response for a specific historical drift scan."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scanned_at: datetime
    status: ReportStatus
    total_drifts: int
    configuration_drifts: int
    runtime_changes: int
    high_severity: int
    medium_severity: int
    low_severity: int
    drifts: list[DriftRecord]
