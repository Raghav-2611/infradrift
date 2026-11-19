import React, { useState, useEffect } from 'react';
import {
  FileText,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  ShieldAlert,
  ChevronDown,
  ChevronRight,
  Eye,
  RefreshCw,
  PlusCircle,
  Edit,
  Trash2,
  RefreshCcw,
  MinusCircle,
  HelpCircle,
  ThumbsUp,
  ThumbsDown,
  Lock,
  Hash,
  UserCheck,
  Check,
  X
} from 'lucide-react';
import {
  approveReconciliationPlan,
  rejectReconciliationPlan,
  fetchExecutionReadiness,
  generateReconciliationPlan,
  fetchLatestReconciliationPlan
} from '../services/api';
import './ReconciliationPlanView.css';

/**
 * Action badge styling helper
 */
const getActionBadge = (action) => {
  switch (action) {
    case 'create':
      return {
        label: 'CREATE',
        icon: PlusCircle,
        className: 'action-badge action-create'
      };
    case 'update':
      return {
        label: 'UPDATE',
        icon: Edit,
        className: 'action-badge action-update'
      };
    case 'delete':
      return {
        label: 'DELETE',
        icon: Trash2,
        className: 'action-badge action-delete'
      };
    case 'replace':
      return {
        label: 'REPLACE',
        icon: RefreshCcw,
        className: 'action-badge action-replace'
      };
    case 'no-op':
      return {
        label: 'NO-OP',
        icon: MinusCircle,
        className: 'action-badge action-noop'
      };
    default:
      return {
        label: (action || 'UNKNOWN').toUpperCase(),
        icon: HelpCircle,
        className: 'action-badge'
      };
  }
};

/**
 * Status badge styling helper
 */
const getStatusBadge = (status) => {
  switch (status) {
    case 'APPROVED':
      return {
        label: 'APPROVED',
        icon: CheckCircle2,
        className: 'status-badge status-approved'
      };
    case 'REJECTED':
      return {
        label: 'REJECTED',
        icon: XCircle,
        className: 'status-badge status-rejected'
      };
    case 'EXPIRED':
      return {
        label: 'EXPIRED',
        icon: Clock,
        className: 'status-badge status-expired'
      };
    case 'EXECUTED':
    case 'APPLIED':
      return {
        label: 'EXECUTED',
        icon: CheckCircle2,
        className: 'status-badge status-executed'
      };
    case 'PENDING_REVIEW':
    default:
      return {
        label: 'PENDING REVIEW',
        icon: Clock,
        className: 'status-badge status-pending'
      };
  }
};

export const ReconciliationPlanView = ({
  plan: propPlan,
  isLoading: propLoading,
  error: propError,
  onGenerateNewPlan: propOnGenerateNewPlan,
  onPlanUpdated: propOnPlanUpdated
}) => {
  const isControlled = propPlan !== undefined || propLoading !== undefined || propOnGenerateNewPlan !== undefined;

  const [internalPlan, setInternalPlan] = useState(null);
  const [internalLoading, setInternalLoading] = useState(false);
  const [internalError, setInternalError] = useState(null);

  const plan = isControlled ? propPlan : internalPlan;
  const isLoading = isControlled ? propLoading : internalLoading;
  const error = isControlled ? propError : internalError;

  const [expandedResources, setExpandedResources] = useState({});
  const [filterAction, setFilterAction] = useState('ALL');

  // Approval / Rejection form states
  const [approverName, setApproverName] = useState('');
  const [approvalComment, setApprovalComment] = useState('');
  const [rejecterName, setRejecterName] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [isSubmittingAction, setIsSubmittingAction] = useState(false);
  const [actionError, setActionError] = useState(null);

  // Execution Readiness state
  const [readinessData, setReadinessData] = useState(null);
  const [isLoadingReadiness, setIsLoadingReadiness] = useState(false);
  const [readinessError, setReadinessError] = useState(null);

  // On mount if not controlled, try to load latest plan
  useEffect(() => {
    if (!isControlled) {
      let isMounted = true;
      fetchLatestReconciliationPlan()
        .then((data) => {
          if (isMounted && data) {
            setInternalPlan(data);
          }
        })
        .catch(() => {
          // No previous plan generated yet
        });
      return () => {
        isMounted = false;
      };
    }
  }, [isControlled]);

  // Fetch readiness whenever plan becomes APPROVED or plan changes
  useEffect(() => {
    if (plan && plan.plan_id && plan.status === 'APPROVED') {
      loadReadiness(plan.plan_id);
    } else {
      setReadinessData(null);
      setReadinessError(null);
    }
    setShowRejectForm(false);
    setActionError(null);
  }, [plan?.plan_id, plan?.status]);

  const handleGenerate = async () => {
    if (propOnGenerateNewPlan) {
      return propOnGenerateNewPlan();
    }
    try {
      setInternalLoading(true);
      setInternalError(null);
      const res = await generateReconciliationPlan();
      setInternalPlan(res);
    } catch (err) {
      setInternalError(err.message || 'Failed to generate plan');
    } finally {
      setInternalLoading(false);
    }
  };

  const loadReadiness = async (planId) => {
    try {
      setIsLoadingReadiness(true);
      setReadinessError(null);
      const res = await fetchExecutionReadiness(planId);
      setReadinessData(res);
    } catch (err) {
      setReadinessError(err.message || 'Failed to inspect execution readiness');
    } finally {
      setIsLoadingReadiness(false);
    }
  };

  const toggleResource = (address) => {
    setExpandedResources((prev) => ({
      ...prev,
      [address]: !prev[address]
    }));
  };

  const handleApprove = async () => {
    if (!approverName.trim()) {
      setActionError('Approver name or ID is required.');
      return;
    }
    try {
      setIsSubmittingAction(true);
      setActionError(null);
      const updated = await approveReconciliationPlan(plan.plan_id, {
        approved_by: approverName.trim(),
        approval_comment: approvalComment.trim() || undefined
      });
      if (propOnPlanUpdated) {
        propOnPlanUpdated(updated);
      } else {
        setInternalPlan(updated);
      }
    } catch (err) {
      setActionError(err.message || 'Approval failed.');
    } finally {
      setIsSubmittingAction(false);
    }
  };

  const handleReject = async () => {
    if (!rejecterName.trim()) {
      setActionError('Rejecter name or ID is required.');
      return;
    }
    if (!rejectionReason.trim()) {
      setActionError('A valid rejection reason is required.');
      return;
    }
    try {
      setIsSubmittingAction(true);
      setActionError(null);
      const updated = await rejectReconciliationPlan(plan.plan_id, {
        rejected_by: rejecterName.trim(),
        rejection_reason: rejectionReason.trim()
      });
      if (propOnPlanUpdated) {
        propOnPlanUpdated(updated);
      } else {
        setInternalPlan(updated);
      }
    } catch (err) {
      setActionError(err.message || 'Rejection failed.');
    } finally {
      setIsSubmittingAction(false);
    }
  };

  if (isLoading) {
    return (
      <div className="rec-plan-loading">
        <RefreshCw className="spinner-icon" size={32} />
        <p>Generating Terraform reconciliation plan safely...</p>
        <span className="rec-plan-subtext">Executing terraform plan in read-only analysis mode</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rec-plan-error">
        <AlertTriangle size={36} className="error-icon" />
        <h3>Failed to Generate Reconciliation Plan</h3>
        <p className="error-message">{error}</p>
        <button className="btn-secondary" onClick={handleGenerate}>
          Retry Plan Generation
        </button>
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="rec-plan-empty">
        <FileText size={48} className="empty-icon" />
        <h3>No Reconciliation Plan Generated</h3>
        <p>
          Generate a fresh, safe Terraform reconciliation plan to preview exact changes
          without applying modifications to cloud infrastructure.
        </p>
        <button className="btn-primary" onClick={handleGenerate}>
          Generate Safe Plan
        </button>
      </div>
    );
  }

  const {
    plan_id,
    created_at,
    expires_at,
    status = 'PENDING_REVIEW',
    plan_hash,
    approved_at,
    approved_by,
    approval_comment,
    rejected_at,
    rejected_by,
    rejection_reason,
    summary = {},
    resource_changes = [],
    has_destructive_changes,
    has_changes
  } = plan;

  const filteredResources = resource_changes.filter((rc) => {
    if (filterAction === 'ALL') return true;
    return rc.action === filterAction.toLowerCase();
  });

  const statusBadge = getStatusBadge(status);
  const StatusIcon = statusBadge.icon;

  return (
    <div className="rec-plan-container">
      {/* Top Banner: Safe Mode Notice */}
      <div className="rec-safe-mode-banner">
        <ShieldAlert size={20} className="banner-shield-icon" />
        <div className="banner-content">
          <div className="banner-title">
            Safe Reconciliation Environment — Phase 2A Active
          </div>
          <div className="banner-desc">
            Execution remains permanently locked in Phase 2A. Infrastructure mutation via
            <code>terraform apply</code> is strictly blocked until Phase 2B multi-signature approval.
          </div>
        </div>
        <button
          className="btn-secondary btn-sm"
          onClick={handleGenerate}
          title="Generate a brand new plan"
        >
          <RefreshCw size={14} /> Refresh Plan
        </button>
      </div>

      {/* Plan Header Info Card */}
      <div className="rec-plan-header-card">
        <div className="rec-header-primary">
          <div className="rec-title-group">
            <span className={statusBadge.className}>
              <StatusIcon size={14} /> {statusBadge.label}
            </span>
            <span className="plan-id-tag" title="Unique Plan UUID">
              Plan ID: <code>{plan_id}</code>
            </span>
            {plan_hash && (
              <span className="plan-hash-tag" title={`SHA-256: ${plan_hash}`}>
                <Hash size={12} /> {plan_hash.substring(0, 12)}...
              </span>
            )}
          </div>
          <div className="rec-timestamp">
            <Clock size={14} /> Generated: {new Date(created_at).toLocaleString()}
            {expires_at && (
              <span className="rec-expiry" title="TTL Expiration">
                {' '}• Expires: {new Date(expires_at).toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>

        {/* Audit Details Bar (if approved or rejected) */}
        {status === 'APPROVED' && (
          <div className="rec-audit-banner approval-audit">
            <UserCheck size={18} className="audit-icon approved-icon" />
            <div className="audit-details">
              <strong>Approved by {approved_by}</strong> on{' '}
              {approved_at ? new Date(approved_at).toLocaleString() : 'N/A'}
              {approvalComment && (
                <div className="audit-comment">"{approvalComment}"</div>
              )}
            </div>
          </div>
        )}

        {status === 'REJECTED' && (
          <div className="rec-audit-banner rejection-audit">
            <XCircle size={18} className="audit-icon rejected-icon" />
            <div className="audit-details">
              <strong>Rejected by {rejected_by}</strong> on{' '}
              {rejected_at ? new Date(rejected_at).toLocaleString() : 'N/A'}
              {rejection_reason && (
                <div className="audit-comment">Reason: "{rejection_reason}"</div>
              )}
            </div>
          </div>
        )}

        {/* Summary Metrics */}
        <div className="rec-summary-grid">
          <div className="rec-metric-card">
            <div className="metric-val">{summary.total_resources ?? resource_changes.length}</div>
            <div className="metric-lbl">Total Resources</div>
          </div>
          <div className="rec-metric-card create-card">
            <div className="metric-val">+{summary.create ?? 0}</div>
            <div className="metric-lbl">To Create</div>
          </div>
          <div className="rec-metric-card update-card">
            <div className="metric-val">~{summary.update ?? 0}</div>
            <div className="metric-lbl">To Update</div>
          </div>
          <div className="rec-metric-card delete-card">
            <div className="metric-val">-{summary.delete ?? 0}</div>
            <div className="metric-lbl">To Delete</div>
          </div>
          <div className="rec-metric-card replace-card">
            <div className="metric-val">±{summary.replace ?? 0}</div>
            <div className="metric-lbl">To Replace</div>
          </div>
          <div className="rec-metric-card noop-card">
            <div className="metric-val">{summary.no_op ?? 0}</div>
            <div className="metric-lbl">No-Op</div>
          </div>
        </div>

        {/* Destructive Warning Banner */}
        {has_destructive_changes && (
          <div className="destructive-warning-banner">
            <AlertTriangle size={18} />
            <span>
              <strong>Destructive Actions Detected:</strong> This plan proposes resource deletion or replacement.
              Explicit review and confirmation required.
            </span>
          </div>
        )}

        {!has_changes && (
          <div className="no-changes-banner">
            <CheckCircle2 size={18} />
            <span>No changes required. Infrastructure matches desired Terraform state.</span>
          </div>
        )}
      </div>

      {/* Action Error Message */}
      {actionError && (
        <div className="rec-action-error-banner">
          <AlertTriangle size={16} />
          <span>{actionError}</span>
        </div>
      )}

      {/* PHASE 2A: APPROVAL / REJECTION WORKFLOW GATE */}
      {status === 'PENDING_REVIEW' && (
        <div className="rec-approval-gate-card">
          <div className="approval-gate-header">
            <h4>
              <ShieldAlert size={18} className="gate-icon" /> Safe Approval Gate
            </h4>
            <span className="gate-subtitle">
              Verify plan diffs below before approving. Approval verifies hash integrity against the immutable <code>.tfplan</code> file.
            </span>
          </div>

          {!showRejectForm ? (
            <div className="approval-actions-bar">
              <div className="approval-input-row">
                <input
                  type="text"
                  placeholder="Approver Name or ID (required)"
                  value={approverName}
                  onChange={(e) => setApproverName(e.target.value)}
                  className="rec-input approver-name-input"
                  disabled={isSubmittingAction}
                />
                <input
                  type="text"
                  placeholder="Optional approval comment (e.g., reviewed with team)"
                  value={approvalComment}
                  onChange={(e) => setApprovalComment(e.target.value)}
                  className="rec-input approval-comment-input"
                  disabled={isSubmittingAction}
                />
              </div>
              <div className="approval-buttons-group">
                <button
                  className="btn-approve"
                  onClick={handleApprove}
                  disabled={isSubmittingAction || !approverName.trim()}
                >
                  <ThumbsUp size={16} />
                  {isSubmittingAction ? 'Approving...' : 'Approve Plan'}
                </button>
                <button
                  className="btn-reject-toggle"
                  onClick={() => setShowRejectForm(true)}
                  disabled={isSubmittingAction}
                >
                  <ThumbsDown size={16} /> Reject Plan
                </button>
              </div>
            </div>
          ) : (
            <div className="rejection-form-panel">
              <div className="rejection-form-title">
                <XCircle size={16} className="rejection-panel-icon" /> Reject Reconciliation Plan
              </div>
              <div className="approval-input-row">
                <input
                  type="text"
                  placeholder="Rejecter Name or ID (required)"
                  value={rejecterName}
                  onChange={(e) => setRejecterName(e.target.value)}
                  className="rec-input rejecter-name-input"
                  disabled={isSubmittingAction}
                />
                <input
                  type="text"
                  placeholder="Rejection Reason (required, e.g., destructive replace not approved)"
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  className="rec-input rejection-reason-input"
                  disabled={isSubmittingAction}
                />
              </div>
              <div className="rejection-buttons-group">
                <button
                  className="btn-confirm-reject"
                  onClick={handleReject}
                  disabled={isSubmittingAction || !rejecterName.trim() || !rejectionReason.trim()}
                >
                  <X size={16} />
                  {isSubmittingAction ? 'Rejecting...' : 'Confirm Rejection'}
                </button>
                <button
                  className="btn-cancel-reject"
                  onClick={() => {
                    setShowRejectForm(false);
                    setActionError(null);
                  }}
                  disabled={isSubmittingAction}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* PHASE 2A: EXECUTION READINESS PANEL (Shown when Approved) */}
      {status === 'APPROVED' && (
        <div className="rec-readiness-card">
          <div className="readiness-header">
            <div className="readiness-title-row">
              <h4>
                <Lock size={18} className="readiness-icon" /> Execution Readiness Inspection
              </h4>
              <button
                className="btn-refresh-readiness"
                onClick={() => loadReadiness(plan.plan_id)}
                disabled={isLoadingReadiness}
                title="Refresh readiness check"
              >
                <RefreshCw size={13} className={isLoadingReadiness ? 'spinner-icon' : ''} /> Check
              </button>
            </div>
            {readinessData && (
              <span
                className={`readiness-pill ${
                  readinessData.is_ready ? 'eligible' : 'ineligible'
                }`}
              >
                {readinessData.is_ready ? 'ELIGIBLE FOR EXECUTION' : 'INELIGIBLE FOR EXECUTION'}
              </span>
            )}
          </div>

          {isLoadingReadiness && (
            <div className="readiness-loading">
              <RefreshCw className="spinner-icon" size={16} /> Checking approval state, artifact integrity, TTL freshness, and lock status...
            </div>
          )}

          {readinessError && (
            <div className="readiness-error">
              <AlertTriangle size={14} /> {readinessError}
            </div>
          )}

          {readinessData && readinessData.checks && (
            <div className="readiness-checks-list">
              {readinessData.checks.map((chk, idx) => (
                <div
                  key={idx}
                  className={`readiness-check-item ${chk.passed ? 'passed' : 'failed'}`}
                >
                  <div className="check-status-icon">
                    {chk.passed ? (
                      <Check size={16} className="pass-icon" />
                    ) : (
                      <X size={16} className="fail-icon" />
                    )}
                  </div>
                  <div className="check-details">
                    <div className="check-name">{chk.name}</div>
                    <div className="check-message">{chk.message}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Phase 2A Safe Execution Safeguard Notice */}
          <div className="readiness-safeguard-box">
            <div className="safeguard-note">
              <Lock size={14} />
              <span>
                <strong>Execution Permanently Locked:</strong> Execution will be unlocked in Phase 2B.
                Under Phase 2A, readiness validates all technical and security prerequisites without mutating state.
              </span>
            </div>
            <button
              className="btn-execute-disabled"
              disabled
              title="Execution disabled until Phase 2B"
            >
              <Lock size={14} /> Execution Disabled (Phase 2A Readiness Only)
            </button>
          </div>
        </div>
      )}

      {/* Filter / Filter Bar */}
      <div className="rec-filter-bar">
        <div className="filter-title">
          <span>Proposed Resource Actions ({filteredResources.length}):</span>
        </div>
        <div className="filter-buttons">
          {['ALL', 'CREATE', 'UPDATE', 'DELETE', 'REPLACE', 'NO-OP'].map((act) => (
            <button
              key={act}
              className={`filter-btn ${filterAction === act ? 'active' : ''}`}
              onClick={() => setFilterAction(act)}
            >
              {act}
            </button>
          ))}
        </div>
      </div>

      {/* Resource Changes List */}
      <div className="rec-resources-list">
        {filteredResources.length === 0 ? (
          <div className="no-resources-found">
            <p>No resources found for the filter '{filterAction}'.</p>
          </div>
        ) : (
          filteredResources.map((rc) => {
            const isExpanded = !!expandedResources[rc.address];
            const badge = getActionBadge(rc.action);
            const BadgeIcon = badge.icon;

            return (
              <div
                key={rc.address}
                className={`rec-resource-card action-${rc.action} ${
                  rc.is_destructive ? 'is-destructive' : ''
                }`}
              >
                <div
                  className="rec-resource-summary-row"
                  onClick={() => toggleResource(rc.address)}
                >
                  <div className="res-expand-toggle">
                    {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                  </div>
                  <div className="res-badge-wrap">
                    <span className={badge.className}>
                      <BadgeIcon size={14} /> {badge.label}
                    </span>
                  </div>
                  <div className="res-address-info">
                    <div className="res-address">
                      <code>{rc.address}</code>
                    </div>
                    <div className="res-type-name">
                      <span>Type: <code>{rc.type}</code></span>
                      <span className="res-name-tag">Name: <code>{rc.name}</code></span>
                    </div>
                  </div>
                  {rc.is_destructive && (
                    <span className="destructive-pill" title="Causes downtime or deletion">
                      <AlertTriangle size={12} /> DESTRUCTIVE
                    </span>
                  )}
                </div>

                {/* Expanded Details Diff View */}
                {isExpanded && (
                  <div className="rec-resource-details-panel">
                    <div className="rec-diff-grid">
                      {/* Before State */}
                      <div className="rec-diff-col before-col">
                        <div className="diff-col-header">
                          <Eye size={14} /> Prior State (Before)
                        </div>
                        <div className="diff-col-content">
                          {rc.before ? (
                            <pre>{JSON.stringify(rc.before, null, 2)}</pre>
                          ) : (
                            <span className="null-state">No prior state (New resource)</span>
                          )}
                        </div>
                      </div>

                      {/* After State */}
                      <div className="rec-diff-col after-col">
                        <div className="diff-col-header">
                          <Eye size={14} /> Planned State (After)
                        </div>
                        <div className="diff-col-content">
                          {rc.after ? (
                            <pre>{JSON.stringify(rc.after, null, 2)}</pre>
                          ) : (
                            <span className="null-state">Resource will be deleted</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default ReconciliationPlanView;
