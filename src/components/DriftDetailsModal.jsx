import React from 'react';
import { 
  X, 
  Server, 
  ArrowRight, 
  HelpCircle, 
  Zap, 
  DollarSign,
  CheckCircle2,
  Lock
} from 'lucide-react';
import { getDriftImpact, getDriftRecommendation } from '../utils/driftAnalysis';
import './DriftDetailsModal.css';

export function DriftDetailsModal({ drift, onClose }) {
  if (!drift) return null;

  const impact = getDriftImpact(drift);
  const recommendation = getDriftRecommendation(drift);

  const isHigh = drift.severity === 'HIGH' || drift.severity === 'CRITICAL';
  const isMedium = drift.severity === 'MEDIUM';

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="drift-detail-modal" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header">
          <div className="modal-title-group">
            <div className="modal-badge-row">
              <span className={`detail-severity-pill mono ${
                isHigh ? 'severity-high' : isMedium ? 'severity-medium' : 'severity-low'
              }`}>
                {drift.severity} SEVERITY
              </span>
              <span className={`detail-category-tag mono ${drift.category}`}>
                {drift.category}
              </span>
              <span className="detail-status-pill mono">
                STATUS: {drift.status}
              </span>
            </div>
            <h3 className="modal-resource-title mono">
              <Server size={18} className="text-secondary" />
              {drift.resource_name}
            </h3>
          </div>
          <button className="modal-close-btn" onClick={onClose} title="Close detail view">
            <X size={20} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body">
          {/* Section 1: Property and Side-by-Side Diff */}
          <div className="detail-section">
            <h4 className="section-heading mono">PROPERTY COMPARISON</h4>
            <div className="property-banner">
              <span className="prop-label text-muted mono">AFFECTED ATTRIBUTE:</span>
              <span className="prop-value mono">{drift.property}</span>
              <span className="prop-type-badge mono">Type: {drift.resource_type}</span>
            </div>

            <div className="diff-boxes-container">
              <div className="diff-box desired-box">
                <div className="diff-box-header">
                  <span className="diff-label mono">DESIRED STATE (Terraform IaC)</span>
                  <span className="diff-source-tag mono">Target</span>
                </div>
                <div className="diff-code-wrapper">
                  <code className="diff-code mono">{drift.desired_value}</code>
                </div>
                <span className="diff-footer-text text-muted">Declared in infrastructure repository</span>
              </div>

              <div className="diff-arrow-box">
                <ArrowRight size={20} className="diff-arrow" />
              </div>

              <div className="diff-box actual-box">
                <div className="diff-box-header">
                  <span className="diff-label mono">ACTUAL STATE (Live AWS Cloud)</span>
                  <span className="diff-source-tag actual-tag mono">Diverged</span>
                </div>
                <div className="diff-code-wrapper">
                  <code className="diff-code mono">{drift.actual_value}</code>
                </div>
                <span className="diff-footer-text text-muted">Queried live from AWS API</span>
              </div>
            </div>
          </div>

          {/* Section 2: Explanation & Reason from Backend */}
          <div className="detail-section">
            <h4 className="section-heading mono">BACKEND EXPLANATION & CLASSIFICATION</h4>
            <div className="explanation-card">
              <div className="explanation-header">
                <HelpCircle size={18} className="text-blue" />
                <span className="mono text-primary font-semibold">Classification Reason:</span>
              </div>
              <p className="explanation-text">
                {drift.reason}
              </p>
              <div className="classification-notes mono text-muted">
                Engine category: <strong>{drift.category}</strong> • Status flag: <strong>{drift.status}</strong>
              </div>
            </div>
          </div>

          {/* Section 3: Potential Technical Impact */}
          <div className="detail-section">
            <h4 className="section-heading mono">POTENTIAL INFRASTRUCTURE IMPACT</h4>
            <div className="impact-grid">
              <div className="impact-card">
                <div className="impact-header">
                  <Zap size={16} className="text-amber" />
                  <span className="mono impact-title">Operational Risk</span>
                </div>
                <p className="impact-desc text-secondary">
                  {impact.description}
                </p>
              </div>

              <div className="impact-card">
                <div className="impact-header">
                  <DollarSign size={16} className="text-emerald" />
                  <span className="mono impact-title">Cost & Billing Impact</span>
                </div>
                <p className="impact-desc text-secondary">
                  {impact.costImpact}
                </p>
              </div>

              <div className="impact-card full-width">
                <div className="impact-header">
                  <Lock size={16} className="text-blue" />
                  <span className="mono impact-title">Compliance & Security Parity</span>
                </div>
                <p className="impact-desc text-secondary">
                  {impact.complianceImpact}
                </p>
              </div>
            </div>
          </div>

          {/* Section 4: Suggested Corrective Action */}
          <div className="detail-section">
            <h4 className="section-heading mono">RECOMMENDED CORRECTIVE ACTION</h4>
            <div className="action-recommendation-box">
              <div className="action-box-header">
                <span className="mono action-type-pill">{recommendation.actionCategory}</span>
                <span className="mono priority-indicator">Priority: {recommendation.recommendedPriority}</span>
              </div>
              <pre className="action-pre mono">{recommendation.suggestedAction}</pre>
              <div className="action-disclaimer text-muted">
                <CheckCircle2 size={14} className="text-emerald" />
                <span>InfraDrift will never execute automated AWS modifications without human approval.</span>
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="modal-footer">
          <span className="footer-resource-ref mono text-muted">
            ID: {drift.resource_name}.{drift.property}
          </span>
          <button className="btn-secondary" onClick={onClose}>
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
}
