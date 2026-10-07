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
    IN_SYNC = "IN_SYNC"


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


class DriftReport(BaseModel):
    """Top-level response returned by GET /api/drift."""

    total_drifts: int
    status: ReportStatus
    drifts: list[DriftRecord]
