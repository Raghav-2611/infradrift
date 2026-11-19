import React from 'react';
import { 
  Layers, 
  Sliders, 
  Activity, 
  ShieldAlert, 
  AlertTriangle, 
  Info, 
  CheckCircle2, 
  Flame 
} from 'lucide-react';
import './DriftStatsCards.css';

export function DriftStatsCards({ stats, loading }) {
  const isDriftDetected = stats?.status === 'DRIFT_DETECTED';

  return (
    <div className="stats-dashboard-container">
      {/* Primary Status Banner */}
      <div className={`overall-status-card ${isDriftDetected ? 'status-drift-active' : 'status-in-sync'}`}>
        <div className="status-indicator-col">
          <div className="status-icon-ring">
            {isDriftDetected ? (
              <Flame size={26} className="icon-pulse-amber" />
            ) : (
              <CheckCircle2 size={26} className="icon-success-emerald" />
            )}
          </div>
          <div className="status-meta">
            <div className="status-headline-row">
              <span className="overall-label text-muted mono">OVERALL INFRASTRUCTURE STATUS</span>
              <span className={`status-pill mono ${isDriftDetected ? 'pill-alert' : 'pill-sync'}`}>
                {isDriftDetected ? 'DRIFT DETECTED' : '100% IN SYNC'}
              </span>
            </div>
            <h3 className="status-text">
              {isDriftDetected 
                ? `${stats?.total_drifts ?? 0} Divergences Detected Against Terraform Source of Truth`
                : 'All Live AWS Resources Match Declared Infrastructure Code'}
            </h3>
          </div>
        </div>
        <div className="status-secondary-info mono">
          <span className="info-chip">Terraform: v1.5+</span>
          <span className="info-chip">Provider: AWS</span>
          <span className="info-chip">Region: us-east-1</span>
        </div>
      </div>

      {/* Grid of Key Metrics */}
      <div className="stats-grid">
        {/* Total Drifts */}
        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-label mono">TOTAL DRIFTS</span>
            <Layers size={18} className="stat-icon text-muted" />
          </div>
          <div className="stat-value mono">
            {loading ? <span className="skeleton-num">--</span> : (stats?.total_drifts ?? 0)}
          </div>
          <div className="stat-desc text-muted">All active divergences across AWS resources</div>
        </div>

        {/* Configuration Drifts */}
        <div className="stat-card highlight-amber">
          <div className="stat-header">
            <span className="stat-label mono">CONFIGURATION DRIFTS</span>
            <Sliders size={18} className="stat-icon text-amber" />
          </div>
          <div className="stat-value mono text-amber">
            {loading ? <span className="skeleton-num">--</span> : (stats?.configuration_drifts ?? 0)}
          </div>
          <div className="stat-desc text-muted">Spec differences (instance type, AMIs, SGs)</div>
        </div>

        {/* Runtime Changes */}
        <div className="stat-card highlight-blue">
          <div className="stat-header">
            <span className="stat-label mono">RUNTIME CHANGES</span>
            <Activity size={18} className="stat-icon text-blue" />
          </div>
          <div className="stat-value mono text-blue">
            {loading ? <span className="skeleton-num">--</span> : (stats?.runtime_changes ?? 0)}
          </div>
          <div className="stat-desc text-muted">Ephemeral attributes (IPs, DNS, power state)</div>
        </div>

        {/* High Severity */}
        <div className="stat-card highlight-red">
          <div className="stat-header">
            <span className="stat-label mono">HIGH SEVERITY</span>
            <ShieldAlert size={18} className="stat-icon text-red" />
          </div>
          <div className="stat-value mono text-red">
            {loading ? <span className="skeleton-num">--</span> : (stats?.high_severity ?? 0)}
          </div>
          <div className="stat-desc text-muted">Urgent drift impacting sizing or security</div>
        </div>

        {/* Medium Severity */}
        <div className="stat-card highlight-orange">
          <div className="stat-header">
            <span className="stat-label mono">MEDIUM SEVERITY</span>
            <AlertTriangle size={18} className="stat-icon text-orange" />
          </div>
          <div className="stat-value mono text-orange">
            {loading ? <span className="skeleton-num">--</span> : (stats?.medium_severity ?? 0)}
          </div>
          <div className="stat-desc text-muted">Configuration divergence with moderate risk</div>
        </div>

        {/* Low Severity */}
        <div className="stat-card highlight-yellow">
          <div className="stat-header">
            <span className="stat-label mono">LOW SEVERITY</span>
            <Info size={18} className="stat-icon text-yellow" />
          </div>
          <div className="stat-value mono text-yellow">
            {loading ? <span className="skeleton-num">--</span> : (stats?.low_severity ?? 0)}
          </div>
          <div className="stat-desc text-muted">Transient, tags, or dependent side-effects</div>
        </div>
      </div>
    </div>
  );
}
