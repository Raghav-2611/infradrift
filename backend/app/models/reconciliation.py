"""
models/reconciliation.py
Pydantic models for Safe Reconciliation plans, actions, diffs, and summaries.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReconciliationAction(str, Enum):
    """Resource-level action determined by Terraform plan."""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    REPLACE = "REPLACE"
    NO_OP = "NO_OP"


class PlanStatus(str, Enum):
    """Lifecycle status of a reconciliation plan."""
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXECUTED = "EXECUTED"
    APPLIED = "EXECUTED"  # Backward compatibility alias


class ChangedAttribute(BaseModel):
    """Attribute-level diff between before (live) and after (desired) states."""

    model_config = ConfigDict(from_attributes=True)

    property: str
    before: Optional[Any] = None
    after: Optional[Any] = None
    is_sensitive: bool = False


class ResourceChangeRecord(BaseModel):
    """Parsed resource-level planned change."""

    model_config = ConfigDict(from_attributes=True)

    address: str
    resource_type: str
    action: ReconciliationAction
    is_destructive: bool
    change_description: str
    changed_attributes: list[ChangedAttribute] = Field(default_factory=list)
    before: Optional[dict[str, Any]] = None
    after: Optional[dict[str, Any]] = None
    action_reason: Optional[str] = None


class PlanSummary(BaseModel):
    """Statistical summary of proposed changes in a plan."""

    model_config = ConfigDict(from_attributes=True)

    total_resources: int
    create_count: int = 0
    update_count: int = 0
    delete_count: int = 0
    replace_count: int = 0
    no_op_count: int = 0
    total_changes: int = 0
    has_destructive_changes: bool = False


class ReconciliationPlanResponse(BaseModel):
    """Top-level response for POST /api/reconciliation/plan and GET /api/reconciliation/plan/{id}."""

    model_config = ConfigDict(from_attributes=True)

    plan_id: UUID
    generated_at: datetime
    status: PlanStatus = PlanStatus.PENDING_REVIEW
    summary: PlanSummary
    resource_changes: list[ResourceChangeRecord]
    warnings: list[str] = Field(default_factory=list)
    plan_hash: Optional[str] = None
    expires_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approval_comment: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejected_by: Optional[str] = None
    rejection_reason: Optional[str] = None


class PlanApprovalRequest(BaseModel):
    """Request payload for POST /api/reconciliation/plan/{id}/approve."""
    approved_by: str = Field(default="admin", min_length=1, max_length=128)
    comment: Optional[str] = Field(default=None, max_length=512)


class PlanRejectionRequest(BaseModel):
    """Request payload for POST /api/reconciliation/plan/{id}/reject."""
    rejected_by: str = Field(default="admin", min_length=1, max_length=128)
    reason: str = Field(..., min_length=1, max_length=512)


class ReadinessCheckItem(BaseModel):
    """Single readiness verification item."""
    name: str
    passed: bool
    detail: str


class ExecutionReadinessResponse(BaseModel):
    """Response payload for GET /api/reconciliation/plan/{id}/readiness."""
    plan_id: UUID
    is_ready: bool
    status: PlanStatus
    checks: list[ReadinessCheckItem]
    ineligibility_reasons: list[str] = Field(default_factory=list)
    checked_at: datetime
    execution_blocked_reason: str = "Execution permanently locked: Phase 2A readiness inspection only. No mutating actions allowed."

