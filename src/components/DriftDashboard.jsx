import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  RefreshCw, 
  Clock, 
  AlertCircle,
  Wifi,
  WifiOff,
  Layers,
  Lightbulb,
  Database,
  GitMerge,
  BarChart3,
  Play,
  Pause
} from 'lucide-react';
import { fetchDriftReport, checkBackendHealth, getApiBaseUrl } from '../services/api';
import { DriftStatsCards } from './DriftStatsCards';
import { DriftTable } from './DriftTable';
import { DriftDetailsModal } from './DriftDetailsModal';
import { RecommendationsPanel } from './RecommendationsPanel';
import { FutureReconciliationModule, FutureMonitoringModule } from './FutureModules';
import { DriftHistoryView } from './DriftHistoryView';
import './DriftDashboard.css';

const AUTO_REFRESH_INTERVAL_SECONDS = 45;

export function DriftDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [backendHealth, setBackendHealth] = useState({ connected: false, checking: true });
  const [lastUpdated, setLastUpdated] = useState(null);
  const [selectedDrift, setSelectedDrift] = useState(null);
  const [activeTab, setActiveTab] = useState('detection');
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
  const [countdown, setCountdown] = useState(AUTO_REFRESH_INTERVAL_SECONDS);

  const isMountedRef = useRef(true);
  const countdownTimerRef = useRef(null);

  // Check backend health
  const checkHealth = useCallback(async () => {
    try {
      const health = await checkBackendHealth();
      if (isMountedRef.current) {
        setBackendHealth({ ...health, checking: false });
      }
    } catch {
      if (isMountedRef.current) {
        setBackendHealth({ connected: false, checking: false });
      }
    }
  }, []);

  // Fetch real drift data from FastAPI backend
  const fetchData = useCallback(async (isBackground = false) => {
    if (!isBackground) {
      setLoading(true);
    }
    setError(null);

    try {
      // Parallel health ping and drift query
      const [report] = await Promise.all([
        fetchDriftReport(),
        checkHealth()
      ]);

      if (isMountedRef.current) {
        setData(report);
        setLastUpdated(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
        setCountdown(AUTO_REFRESH_INTERVAL_SECONDS);
      }
    } catch (err) {
      console.error('Failed to fetch drift report from backend:', err);
      if (isMountedRef.current) {
        setError(err.message || 'Unable to connect to FastAPI backend.');
        setBackendHealth({ connected: false, checking: false });
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [checkHealth]);

  // Initial load
  useEffect(() => {
    isMountedRef.current = true;
    fetchData();
    return () => {
      isMountedRef.current = false;
    };
  }, [fetchData]);

  // Synchronize hash navigation (e.g. #recommendations, #history, #reconciliation)
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '');
      if (hash === 'recommendations') setActiveTab('recommendations');
      else if (hash === 'reconciliation') setActiveTab('reconciliation');
      else if (hash === 'history') setActiveTab('history');
      else if (hash === 'monitoring') setActiveTab('monitoring');
      else if (hash === 'live-drift' || hash === 'detection') setActiveTab('detection');
    };

    handleHashChange();
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // Auto-refresh interval (30-60s) with clean unmount handling
  useEffect(() => {
    if (!autoRefreshEnabled) return;

    const intervalId = setInterval(() => {
      fetchData(true);
    }, AUTO_REFRESH_INTERVAL_SECONDS * 1000);

    return () => {
      clearInterval(intervalId);
    };
  }, [autoRefreshEnabled, fetchData]);

  // Countdown timer for next refresh
  useEffect(() => {
    if (!autoRefreshEnabled) return;

    countdownTimerRef.current = setInterval(() => {
      setCountdown((prev) => (prev <= 1 ? AUTO_REFRESH_INTERVAL_SECONDS : prev - 1));
    }, 1000);

    return () => {
      clearInterval(countdownTimerRef.current);
    };
  }, [autoRefreshEnabled]);

  const drifts = data?.drifts || [];
  const backendBaseUrl = getApiBaseUrl();

  return (
    <section id="live-drift" className="section drift-dashboard-section">
      <div className="container">
        {/* Top Header & Connection Bar */}
        <div className="dashboard-header">
          <div className="header-left">
            <div className="pill-label">
              <span className={`pill-dot ${backendHealth.connected ? 'dot-connected' : 'dot-disconnected'}`}></span>
              <span>LIVE DRIFT DETECTION ENGINE</span>
            </div>
            <h2 className="dashboard-title">Real-Time Infrastructure State</h2>
            <p className="dashboard-subtitle text-secondary">
              Synchronized audit comparing live AWS cloud state against Terraform desired configuration.
            </p>
          </div>

          <div className="header-actions">
            {/* Backend Connection Indicator */}
            <div className={`backend-status-pill mono ${backendHealth.connected ? 'online' : 'offline'}`} title={`Backend: ${backendBaseUrl}`}>
              {backendHealth.connected ? (
                <>
                  <Wifi size={14} className="status-wifi-icon text-emerald" />
                  <span className="backend-conn-text">Backend: Online</span>
                </>
              ) : (
                <>
                  <WifiOff size={14} className="status-wifi-icon text-red" />
                  <span className="backend-conn-text">Backend: Disconnected</span>
                </>
              )}
            </div>

            {/* Manual Refresh Button */}
            <button 
              className={`scan-btn ${loading ? 'scanning' : ''}`}
              onClick={() => fetchData(false)}
              disabled={loading}
              title="Execute live terraform refresh-only scan"
            >
              <RefreshCw size={16} className={loading ? 'spin-icon' : ''} />
              <span>{loading ? 'Auditing State...' : 'Scan Drift Now'}</span>
            </button>
          </div>
        </div>

        {/* Status & Auto-refresh Meta Strip */}
        <div className="dashboard-meta-strip">
          <div className="meta-left">
            {lastUpdated && (
              <span className="meta-item mono text-muted">
                <Clock size={13} />
                Last audit: <strong>{lastUpdated}</strong>
              </span>
            )}
            <span className="meta-item mono text-muted">
              Endpoint: <code className="endpoint-code">{backendBaseUrl}/api/drift</code>
            </span>
          </div>

          <div className="meta-right">
            <button 
              className={`auto-refresh-toggle mono ${autoRefreshEnabled ? 'enabled' : 'paused'}`}
              onClick={() => setAutoRefreshEnabled(!autoRefreshEnabled)}
              title={autoRefreshEnabled ? 'Click to pause auto-refresh' : 'Click to enable auto-refresh'}
            >
              {autoRefreshEnabled ? <Pause size={12} /> : <Play size={12} />}
              <span>
                {autoRefreshEnabled ? `Auto-refresh in ${countdown}s` : 'Auto-refresh paused'}
              </span>
            </button>
          </div>
        </div>

        {/* Backend Error Alert Box */}
        {error && (
          <div className="error-box">
            <AlertCircle size={22} className="error-icon" />
            <div className="error-content">
              <h4 className="error-title">FastAPI Backend Connection Failure</h4>
              <p className="error-msg">{error}</p>
              <p className="error-tip text-muted">
                Connecting to <code>{backendBaseUrl}</code>. Ensure the FastAPI service is active and the EC2 security group allows ingress on port 8000.
              </p>
            </div>
            <button className="btn-secondary retry-btn" onClick={() => fetchData(false)}>
              Retry Connection
            </button>
          </div>
        )}

        {/* Dashboard Navigation Tabs */}
        <div className="dashboard-nav-tabs">
          <button 
            className={`dash-tab-btn mono ${activeTab === 'detection' ? 'active' : ''}`}
            onClick={() => setActiveTab('detection')}
          >
            <Layers size={16} />
            <span>Drift Detection</span>
            <span className="dash-tab-count">{drifts.length}</span>
          </button>

          <button 
            className={`dash-tab-btn mono ${activeTab === 'recommendations' ? 'active' : ''}`}
            onClick={() => setActiveTab('recommendations')}
          >
            <Lightbulb size={16} />
            <span>Recommendations</span>
            <span className="dash-tab-count">{drifts.length}</span>
          </button>

          <button 
            className={`dash-tab-btn mono ${activeTab === 'reconciliation' ? 'active' : ''}`}
            onClick={() => setActiveTab('reconciliation')}
          >
            <GitMerge size={16} />
            <span>Reconciliation</span>
            <span className="future-pill mono">Safe Apply</span>
          </button>

          <button 
            className={`dash-tab-btn mono ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveTab('history')}
          >
            <Database size={16} />
            <span>Drift History</span>
            <span className="future-pill mono">PostgreSQL</span>
          </button>

          <button 
            className={`dash-tab-btn mono ${activeTab === 'monitoring' ? 'active' : ''}`}
            onClick={() => setActiveTab('monitoring')}
          >
            <BarChart3 size={16} />
            <span>Monitoring</span>
            <span className="future-pill mono">Prometheus</span>
          </button>
        </div>

        {/* Dynamic Tab Content */}
        {activeTab === 'detection' && (
          <div className="tab-pane fade-in">
            {/* Real Statistics Cards */}
            <DriftStatsCards stats={data} loading={loading} />

            {/* Drift Records Table with Filtering */}
            <DriftTable 
              drifts={drifts} 
              selectedDrift={selectedDrift}
              onSelectDrift={(drift) => setSelectedDrift(drift)}
              loading={loading}
            />
          </div>
        )}

        {activeTab === 'recommendations' && (
          <div className="tab-pane fade-in">
            <RecommendationsPanel 
              drifts={drifts} 
              onSelectDrift={(drift) => setSelectedDrift(drift)}
            />
          </div>
        )}

        {activeTab === 'reconciliation' && (
          <div className="tab-pane fade-in">
            <FutureReconciliationModule />
          </div>
        )}

        {activeTab === 'history' && (
          <div className="tab-pane fade-in">
            <DriftHistoryView />
          </div>
        )}

        {activeTab === 'monitoring' && (
          <div className="tab-pane fade-in">
            <FutureMonitoringModule />
          </div>
        )}

        {/* Detailed Drift View / Analysis Modal */}
        {selectedDrift && (
          <DriftDetailsModal 
            drift={selectedDrift} 
            onClose={() => setSelectedDrift(null)} 
          />
        )}
      </div>
    </section>
  );
}
