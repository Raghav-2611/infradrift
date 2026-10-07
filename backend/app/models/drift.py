"""
models/drift.py
Pydantic models that describe infrastructure drift records
and the top-level API response.
"""

from enum import Enum
from pydantic import BaseModel


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

    resource_name: str
    resource_type: str
    property: str
    desired_value: str
    actual_value: str
    severity: Severity
    status: DriftStatus
    category: DriftCategory
    reason: str


class DriftReport(BaseModel):
    """Top-level response returned by GET /api/drift."""

    total_drifts: int
    configuration_drifts: int
    runtime_changes: int
    status: ReportStatus
    drifts: list[DriftRecord]
