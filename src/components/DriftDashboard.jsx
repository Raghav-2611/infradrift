import React, { useState, useEffect, useCallback } from 'react';
import { 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle2, 
  Layers, 
  Sliders, 
  Activity, 
  Clock, 
  AlertCircle,
  ShieldAlert,
  ArrowRight,
  Server
} from 'lucide-react';
import './DriftDashboard.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function DriftDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [filterCategory, setFilterCategory] = useState('ALL');

  const fetchDriftData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_URL}/api/drift`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();
      setData(result);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err) {
      console.error('Failed to fetch drift report:', err);
      setError(err.message || `Unable to connect to FastAPI backend at ${API_URL}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDriftData();
  }, [fetchDriftData]);

  const drifts = data?.drifts || [];
  
  const filteredDrifts = drifts.filter((item) => {
    if (filterCategory === 'ALL') return true;
    if (filterCategory === 'CONFIGURATION_DRIFT') return item.category === 'CONFIGURATION_DRIFT';
    if (filterCategory === 'RUNTIME_STATE_CHANGE') {
      return item.category === 'RUNTIME_STATE_CHANGE' || item.category === 'DEPENDENCY_CHANGE';
    }
    return true;
  });

  const isDriftDetected = data?.status === 'DRIFT_DETECTED';

  return (
    <section id="live-drift" className="section drift-dashboard-section">
      <div className="container">
        {/* Section Header */}
        <div className="dashboard-header">
          <div className="header-left">
            <div className="pill-label">
              <span className="pill-dot glow-dot"></span>
              <span>LIVE DRIFT ENGINE</span>
            </div>
            <h2 className="dashboard-title">Infrastructure State Audit</h2>
            <p className="dashboard-subtitle text-secondary">
              Real-time synchronization engine comparing Terraform desired state against AWS runtime environment.
            </p>
          </div>

          <div className="header-actions">
            <button 
              className={`scan-btn ${loading ? 'scanning' : ''}`}
              onClick={fetchDriftData}
              disabled={loading}
              title="Run terraform refresh-only plan"
            >
              <RefreshCw size={16} className={loading ? 'spin-icon' : ''} />
              <span>{loading ? 'Scanning Infrastructure...' : 'Scan Drift Now'}</span>
            </button>
          </div>
        </div>

        {/* System Status Banner */}
        <div className="status-banner-wrapper">
          <div className={`status-banner ${isDriftDetected ? 'has-drift' : 'in-sync'}`}>
            <div className="status-banner-main">
              <div className="status-icon-box">
                {isDriftDetected ? (
                  <AlertTriangle size={24} className="icon-warning" />
                ) : (
                  <CheckCircle2 size={24} className="icon-success" />
                )}
              </div>
              <div className="status-banner-text">
                <div className="status-title-row">
                  <span className="status-badge mono">
                    {isDriftDetected ? 'DRIFT DETECTED' : '100% IN SYNC'}
                  </span>
                  {lastUpdated && (
                    <span className="timestamp mono text-muted">
                      <Clock size={12} /> Last scan: {lastUpdated}
                    </span>
                  )}
                </div>
                <p className="status-desc text-secondary">
                  {isDriftDetected
                    ? `Found ${data?.total_drifts || 0} infrastructure property mismatches requiring attention.`
                    : 'All AWS resources strictly match Terraform state configuration.'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Metric Overview Cards */}
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-header">
              <span className="metric-label mono">TOTAL DRIFTS</span>
              <Layers size={18} className="metric-icon text-muted" />
            </div>
            <div className="metric-value mono">{loading ? '-' : data?.total_drifts ?? 0}</div>
            <div className="metric-footer text-muted">Detected property discrepancies</div>
          </div>

          <div className="metric-card highlight-amber">
            <div className="metric-header">
              <span className="metric-label mono">CONFIGURATION DRIFT</span>
              <Sliders size={18} className="metric-icon text-amber" />
            </div>
            <div className="metric-value mono text-amber">{loading ? '-' : data?.configuration_drifts ?? 0}</div>
            <div className="metric-footer text-muted">Spec differences (e.g. instance_type)</div>
          </div>

          <div className="metric-card highlight-blue">
            <div className="metric-header">
              <span className="metric-label mono">RUNTIME STATE CHANGES</span>
              <Activity size={18} className="metric-icon text-blue" />
            </div>
            <div className="metric-value mono text-blue">{loading ? '-' : data?.runtime_changes ?? 0}</div>
            <div className="metric-footer text-muted">Runtime attributes (e.g. public_ip)</div>
          </div>
        </div>

        {/* Error Alert Box */}
        {error && (
          <div className="error-box">
            <AlertCircle size={20} className="error-icon" />
            <div className="error-content">
              <h4 className="error-title">Backend Connection Error</h4>
              <p className="error-msg">{error}</p>
              <p className="error-tip text-muted">
                Make sure the FastAPI backend is running via <code>python -m uvicorn app.main:app --reload</code> inside the <code>/backend</code> directory.
              </p>
            </div>
            <button className="btn-secondary retry-btn" onClick={fetchDriftData}>
              Retry
            </button>
          </div>
        )}

        {/* Drift Records List Section */}
        <div className="records-section">
          <div className="records-header">
            <div className="records-tabs">
              <button 
                className={`tab-btn ${filterCategory === 'ALL' ? 'active' : ''}`}
                onClick={() => setFilterCategory('ALL')}
              >
                All Drifts <span className="tab-count mono">{drifts.length}</span>
              </button>
              <button 
                className={`tab-btn ${filterCategory === 'CONFIGURATION_DRIFT' ? 'active' : ''}`}
                onClick={() => setFilterCategory('CONFIGURATION_DRIFT')}
              >
                Configuration <span className="tab-count mono">{data?.configuration_drifts ?? 0}</span>
              </button>
              <button 
                className={`tab-btn ${filterCategory === 'RUNTIME_STATE_CHANGE' ? 'active' : ''}`}
                onClick={() => setFilterCategory('RUNTIME_STATE_CHANGE')}
              >
                Runtime <span className="tab-count mono">{data?.runtime_changes ?? 0}</span>
              </button>
            </div>
          </div>

          {loading ? (
            <div className="loading-container">
              <div className="loading-spinner"></div>
              <p className="loading-text mono">Executing <code>terraform plan -refresh-only</code>...</p>
              <p className="loading-subtext text-muted">Analysing AWS EC2 state and parsing state JSON diff</p>
            </div>
          ) : filteredDrifts.length === 0 ? (
            <div className="empty-state">
              <CheckCircle2 size={40} className="text-emerald" />
              <h3>No drifts found in this category</h3>
              <p className="text-muted">Your infrastructure matches the target configuration.</p>
            </div>
          ) : (
            <div className="drifts-list">
              {filteredDrifts.map((item, index) => {
                const isConfig = item.category === 'CONFIGURATION_DRIFT';
                return (
                  <div key={`${item.resource_name}-${item.property}-${index}`} className={`drift-card ${isConfig ? 'border-amber' : ''}`}>
                    <div className="card-header-row">
                      <div className="resource-info">
                        <Server size={16} className="resource-icon" />
                        <span className="resource-name mono">{item.resource_name}</span>
                        <span className="resource-type-badge mono">{item.resource_type}</span>
                      </div>
                      <div className="badges-row">
                        <span className={`category-badge mono ${item.category}`}>
                          {item.category === 'CONFIGURATION_DRIFT' ? 'CONFIG DRIFT' : 'RUNTIME STATE'}
                        </span>
                        <span className={`severity-badge mono severity-${item.severity?.toLowerCase()}`}>
                          {item.severity}
                        </span>
                      </div>
                    </div>

                    <div className="property-row">
                      <span className="property-label text-muted">Property:</span>
                      <span className="property-name mono">{item.property}</span>
                    </div>

                    <div className="values-comparison">
                      <div className="value-box desired">
                        <span className="value-header mono">DESIRED STATE (Terraform)</span>
                        <code className="value-code mono">{String(item.desired_value ?? 'null')}</code>
                      </div>
                      <div className="comparison-divider">
                        <ArrowRight size={16} className="text-muted" />
                      </div>
                      <div className="value-box actual">
                        <span className="value-header mono">ACTUAL STATE (AWS Cloud)</span>
                        <code className="value-code mono">{String(item.actual_value ?? 'null')}</code>
                      </div>
                    </div>

                    {item.reason && (
                      <div className="reason-row text-muted">
                        <span className="reason-label mono">REASON:</span> {item.reason}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
