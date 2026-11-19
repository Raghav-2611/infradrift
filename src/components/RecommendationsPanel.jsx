import React, { useState } from 'react';
import { 
  Lightbulb, 
  ArrowRight, 
  Server, 
  ShieldCheck
} from 'lucide-react';
import { getDriftRecommendation } from '../utils/driftAnalysis';
import './RecommendationsPanel.css';

export function RecommendationsPanel({ drifts, onSelectDrift }) {
  const [filterPriority, setFilterPriority] = useState('ALL');

  if (!drifts || drifts.length === 0) {
    return (
      <div className="recommendations-container empty-recs">
        <ShieldCheck size={48} className="text-emerald" />
        <h3 className="empty-title">All Infrastructure In Sync</h3>
        <p className="empty-subtitle text-muted">
          No configuration drift detected. No corrective remediation actions are required at this time.
        </p>
      </div>
    );
  }

  const recommendations = drifts.map((drift) => {
    const rec = getDriftRecommendation(drift);
    return {
      drift,
      ...rec,
    };
  });

  const filteredRecs = recommendations.filter((item) => {
    if (filterPriority === 'ALL') return true;
    return item.recommendedPriority === filterPriority;
  });

  return (
    <div className="recommendations-container">
      {/* Banner explaining advisory nature */}
      <div className="advisory-banner">
        <div className="advisory-icon-col">
          <Lightbulb size={22} className="text-amber" />
        </div>
        <div className="advisory-text-col">
          <div className="advisory-title-row">
            <h4 className="advisory-title">Automated Remediation Insights & Playbooks</h4>
            <span className="advisory-badge mono">ADVISORY ONLY</span>
          </div>
          <p className="advisory-desc text-secondary">
            Below are deterministic corrective recommendations generated from detected drift state. 
            <strong> InfraDrift does not execute modifications automatically</strong> — all reconciliation actions require engineer review and approval.
          </p>
        </div>
      </div>

      {/* Filter by Priority */}
      <div className="recs-toolbar">
        <div className="priority-filters">
          <span className="filter-label mono text-muted">FILTER PRIORITY:</span>
          {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map((p) => (
            <button
              key={p}
              className={`priority-tab-btn mono ${filterPriority === p ? 'active' : ''}`}
              onClick={() => setFilterPriority(p)}
            >
              {p}
              {p === 'ALL' && <span className="p-count">{recommendations.length}</span>}
              {p === 'HIGH' && (
                <span className="p-count">
                  {recommendations.filter((r) => r.recommendedPriority === 'HIGH' || r.recommendedPriority === 'CRITICAL').length}
                </span>
              )}
              {p === 'MEDIUM' && (
                <span className="p-count">
                  {recommendations.filter((r) => r.recommendedPriority === 'MEDIUM').length}
                </span>
              )}
              {p === 'LOW' && (
                <span className="p-count">
                  {recommendations.filter((r) => r.recommendedPriority === 'LOW').length}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* List of Recommendation Cards */}
      <div className="recommendations-list">
        {filteredRecs.map(({ drift, whatChanged, whyItMatters, suggestedAction, recommendedPriority, actionCategory }) => {
          const isHigh = recommendedPriority === 'HIGH' || recommendedPriority === 'CRITICAL';
          const isMedium = recommendedPriority === 'MEDIUM';

          return (
            <div 
              key={`rec-${drift.id}`} 
              className={`recommendation-card ${isHigh ? 'border-priority-high' : ''}`}
            >
              <div className="rec-header">
                <div className="rec-resource-meta">
                  <Server size={16} className="text-muted" />
                  <span className="rec-res-name mono">{drift.resource_name}</span>
                  <span className="rec-prop-badge mono">{drift.property}</span>
                </div>
                <div className="rec-badges">
                  <span className="rec-category-tag mono">{actionCategory}</span>
                  <span className={`priority-badge mono ${
                    isHigh ? 'p-high' : isMedium ? 'p-medium' : 'p-low'
                  }`}>
                    PRIORITY: {recommendedPriority}
                  </span>
                </div>
              </div>

              <div className="rec-content-grid">
                {/* 1. What Changed */}
                <div className="rec-item">
                  <div className="rec-item-label mono text-muted">
                    <span className="rec-step-num">1</span> WHAT CHANGED?
                  </div>
                  <p className="rec-item-text">{whatChanged}</p>
                </div>

                {/* 2. Why It Matters */}
                <div className="rec-item">
                  <div className="rec-item-label mono text-muted">
                    <span className="rec-step-num">2</span> WHY IT MATTERS
                  </div>
                  <p className="rec-item-text text-secondary">{whyItMatters}</p>
                </div>

                {/* 3. Suggested Corrective Action */}
                <div className="rec-item full-width">
                  <div className="rec-item-label mono text-muted">
                    <span className="rec-step-num">3</span> SUGGESTED CORRECTIVE ACTION
                  </div>
                  <div className="rec-action-box">
                    <pre className="rec-action-code mono">{suggestedAction}</pre>
                  </div>
                </div>
              </div>

              <div className="rec-footer">
                <span className="rec-audit-source mono text-muted">
                  Detection: Terraform refresh-only vs live AWS EC2
                </span>
                <button 
                  className="btn-inspect-rec mono"
                  onClick={() => onSelectDrift(drift)}
                >
                  <span>Inspect Full Diff</span>
                  <ArrowRight size={14} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
