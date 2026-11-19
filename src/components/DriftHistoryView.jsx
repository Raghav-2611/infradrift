import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Database,
  RefreshCw,
  Clock,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  WifiOff,
  CheckCircle2,
  AlertTriangle,
  X,
  Search,
} from 'lucide-react';
import { fetchDriftHistory, fetchDriftScanDetail } from '../services/api';
import { DriftTable } from './DriftTable';
import { DriftDetailsModal } from './DriftDetailsModal';
import './DriftHistoryView.css';

const PAGE_SIZE = 10;

function formatTimestamp(isoStr) {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    return d.toLocaleString([], {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return isoStr;
  }
}

function StatusBadge({ status }) {
  const s = (status || 'UNKNOWN').toUpperCase();
  let cls = 'hist-status-badge ';
  if (s === 'NO_DRIFT') cls += 'badge-ok';
  else if (s === 'DRIFT_DETECTED') cls += 'badge-drift';
  else cls += 'badge-unknown';

  const label =
    s === 'NO_DRIFT' ? 'No Drift' :
    s === 'DRIFT_DETECTED' ? 'Drift Detected' :
    s;

  const Icon =
    s === 'NO_DRIFT' ? CheckCircle2 :
    s === 'DRIFT_DETECTED' ? AlertTriangle :
    AlertCircle;

  return (
    <span className={cls}>
      <Icon size={11} />
      {label}
    </span>
  );
}

function SeverityPill({ count, level }) {
  if (!count) return null;
  return (
    <span className={`hist-sev-pill sev-${level.toLowerCase()}`}>
      {level[0]}{count}
    </span>
  );
}

function SkeletonRow() {
  return (
    <tr className="hist-skeleton-row">
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <td key={i}><span className="hist-skeleton-cell" /></td>
      ))}
    </tr>
  );
}

function DatabaseUnavailableState({ onRetry }) {
  return (
    <div className="hist-unavailable-box">
      <div className="hist-unavail-icon-wrap">
        <Database size={40} className="hist-unavail-icon" />
      </div>
      <h3 className="hist-unavail-title">History Database Not Connected</h3>
      <p className="hist-unavail-desc">
        PostgreSQL history persistence is not yet configured on this backend instance.
        The live drift detection engine continues to operate normally.
      </p>
      <div className="hist-unavail-info mono">
        <div className="hist-unavail-row">
          <span className="hist-unavail-label">Required:</span>
          <code>DATABASE_URL</code> env var on the EC2 host
        </div>
        <div className="hist-unavail-row">
          <span className="hist-unavail-label">Endpoint:</span>
          <code>GET /api/history</code> returns HTTP 503 until configured
        </div>
        <div className="hist-unavail-row">
          <span className="hist-unavail-label">Setup:</span>
          Set <code>DATABASE_URL=postgresql+psycopg://user:pass@host/db</code> and restart the backend
        </div>
      </div>
      <button className="btn-secondary retry-btn" onClick={onRetry}>
        <RefreshCw size={14} />
        Retry Connection
      </button>
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div className="hist-error-box">
      <AlertCircle size={22} className="error-icon" />
      <div>
        <h4 className="error-title">Failed to Load History</h4>
        <p className="error-msg">{message}</p>
      </div>
      <button className="btn-secondary retry-btn" onClick={onRetry}>
        <RefreshCw size={14} />
        Retry
      </button>
    </div>
  );
}

// ─── Scan Detail Drawer ───────────────────────────────────────────────────────

function ScanDetailDrawer({ scanId, onClose }) {
  const [scan, setScan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedDrift, setSelectedDrift] = useState(null);
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;
    return () => { isMounted.current = false; };
  }, []);

  useEffect(() => {
    if (!scanId) return;
    setLoading(true);
    setError(null);
    setScan(null);

    fetchDriftScanDetail(scanId)
      .then((data) => {
        if (isMounted.current) setScan(data);
      })
      .catch((err) => {
        if (isMounted.current) setError(err.message || 'Failed to load scan detail.');
      })
      .finally(() => {
        if (isMounted.current) setLoading(false);
      });
  }, [scanId]);

  return (
    <div className="hist-drawer-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="hist-drawer">
        {/* Drawer Header */}
        <div className="hist-drawer-header">
          <div className="hist-drawer-title-wrap">
            <Database size={18} className="text-blue" />
            <div>
              <h3 className="hist-drawer-title">Historical Scan Detail</h3>
              {scan && (
                <p className="hist-drawer-subtitle mono">
                  <Clock size={12} /> {formatTimestamp(scan.scanned_at)}
                </p>
              )}
            </div>
          </div>
          <button className="hist-drawer-close" onClick={onClose} title="Close">
            <X size={18} />
          </button>
        </div>

        {/* Drawer Body */}
        <div className="hist-drawer-body">
          {loading && (
            <div className="hist-loading-center">
              <RefreshCw size={28} className="spin-icon text-blue" />
              <p className="mono text-muted">Loading scan records…</p>
            </div>
          )}

          {error && !loading && (
            <div className="hist-drawer-error">
              <AlertCircle size={18} className="error-icon" />
              <p>{error}</p>
            </div>
          )}

          {!loading && !error && scan && (
            <>
              {/* Mini stats */}
              <div className="hist-drawer-stats-row">
                <div className="hist-drawer-stat-card">
                  <span className="hist-drawer-stat-value">{scan.total_drifts}</span>
                  <span className="hist-drawer-stat-label mono">Total Drifts</span>
                </div>
                <div className="hist-drawer-stat-card">
                  <span className="hist-drawer-stat-value">{scan.configuration_drifts}</span>
                  <span className="hist-drawer-stat-label mono">Config Drifts</span>
                </div>
                <div className="hist-drawer-stat-card">
                  <span className="hist-drawer-stat-value">{scan.runtime_changes}</span>
                  <span className="hist-drawer-stat-label mono">Runtime</span>
                </div>
                <div className="hist-drawer-stat-card sev-high">
                  <span className="hist-drawer-stat-value">{scan.high_severity}</span>
                  <span className="hist-drawer-stat-label mono">High</span>
                </div>
                <div className="hist-drawer-stat-card sev-medium">
                  <span className="hist-drawer-stat-value">{scan.medium_severity}</span>
                  <span className="hist-drawer-stat-label mono">Medium</span>
                </div>
                <div className="hist-drawer-stat-card sev-low">
                  <span className="hist-drawer-stat-value">{scan.low_severity}</span>
                  <span className="hist-drawer-stat-label mono">Low</span>
                </div>
              </div>

              {/* Status */}
              <div className="hist-drawer-status-row">
                <span className="mono text-muted" style={{ fontSize: '0.8125rem' }}>Scan Status:</span>
                <StatusBadge status={scan.status} />
                <span className="mono text-muted" style={{ fontSize: '0.75rem', marginLeft: 'auto' }}>
                  ID: {scan.id}
                </span>
              </div>

              {/* Drift table for this scan */}
              {scan.drifts && scan.drifts.length > 0 ? (
                <div className="hist-drawer-table-wrap">
                  <DriftTable
                    drifts={scan.drifts}
                    selectedDrift={selectedDrift}
                    onSelectDrift={setSelectedDrift}
                    loading={false}
                  />
                </div>
              ) : (
                <div className="hist-no-drifts mono">
                  <CheckCircle2 size={24} className="text-emerald" />
                  <p>No drifts recorded in this scan.</p>
                </div>
              )}
            </>
          )}
        </div>

        {/* Drift detail modal inside drawer */}
        {selectedDrift && (
          <DriftDetailsModal
            drift={selectedDrift}
            onClose={() => setSelectedDrift(null)}
          />
        )}
      </div>
    </div>
  );
}

// ─── Main History View ────────────────────────────────────────────────────────

export function DriftHistoryView() {
  const [scans, setScans] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);           // 0-based
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isDatabaseUnavailable, setIsDatabaseUnavailable] = useState(false);
  const [lastFetched, setLastFetched] = useState(null);
  const [selectedScanId, setSelectedScanId] = useState(null);
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;
    return () => { isMounted.current = false; };
  }, []);

  const loadPage = useCallback(async (pageIndex) => {
    setLoading(true);
    setError(null);
    setIsDatabaseUnavailable(false);

    try {
      const result = await fetchDriftHistory(PAGE_SIZE, pageIndex * PAGE_SIZE);
      if (isMounted.current) {
        setScans(result.scans);
        setTotal(result.total);
        setLastFetched(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
      }
    } catch (err) {
      if (isMounted.current) {
        if (err.isDatabaseUnavailable) {
          setIsDatabaseUnavailable(true);
        } else {
          setError(err.message || 'Failed to load scan history.');
        }
      }
    } finally {
      if (isMounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPage(page);
  }, [page, loadPage]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const handlePrev = () => setPage((p) => Math.max(0, p - 1));
  const handleNext = () => setPage((p) => Math.min(totalPages - 1, p + 1));

  // ── Render: DB unavailable ──
  if (!loading && isDatabaseUnavailable) {
    return (
      <div className="hist-view-root">
        <HistoryHeader onRefresh={() => loadPage(page)} loading={loading} lastFetched={null} />
        <DatabaseUnavailableState onRetry={() => loadPage(page)} />
      </div>
    );
  }

  // ── Render: error ──
  if (!loading && error && scans.length === 0) {
    return (
      <div className="hist-view-root">
        <HistoryHeader onRefresh={() => loadPage(page)} loading={loading} lastFetched={null} />
        <ErrorState message={error} onRetry={() => loadPage(page)} />
      </div>
    );
  }

  return (
    <div className="hist-view-root">
      <HistoryHeader onRefresh={() => loadPage(page)} loading={loading} lastFetched={lastFetched} />

      {/* Scan list table */}
      <div className="hist-table-card">
        <div className="hist-table-header-row">
          <div>
            <h3 className="hist-table-title">Scan History</h3>
            {!loading && (
              <p className="hist-table-subtitle mono">
                {total} scan{total !== 1 ? 's' : ''} recorded — click any row to inspect drift records
              </p>
            )}
          </div>
          {total > 0 && (
            <div className="hist-pagination-controls">
              <span className="mono text-muted" style={{ fontSize: '0.75rem' }}>
                Page {page + 1} of {totalPages}
              </span>
              <button
                className="hist-page-btn"
                onClick={handlePrev}
                disabled={page === 0 || loading}
                title="Previous page"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                className="hist-page-btn"
                onClick={handleNext}
                disabled={page >= totalPages - 1 || loading}
                title="Next page"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          )}
        </div>

        <div className="hist-table-wrap">
          <table className="hist-table">
            <thead>
              <tr>
                <th className="mono">Scan Time</th>
                <th className="mono">Status</th>
                <th className="mono">Total Drifts</th>
                <th className="mono">Config</th>
                <th className="mono">Runtime</th>
                <th className="mono">Severity Breakdown</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: PAGE_SIZE }).map((_, i) => <SkeletonRow key={i} />)
              ) : scans.length === 0 ? (
                <tr>
                  <td colSpan={6} className="hist-empty-cell">
                    <div className="hist-empty-state">
                      <Search size={28} className="text-muted" />
                      <p className="mono text-muted">No scans stored yet. Run a drift detection to populate history.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                scans.map((scan) => (
                  <tr
                    key={scan.id}
                    className="hist-data-row"
                    onClick={() => setSelectedScanId(scan.id)}
                    title="Click to view drift records for this scan"
                  >
                    <td className="mono hist-time-cell">
                      <Clock size={12} className="text-muted" />
                      {formatTimestamp(scan.scanned_at)}
                    </td>
                    <td>
                      <StatusBadge status={scan.status} />
                    </td>
                    <td className="mono hist-count-cell">{scan.total_drifts}</td>
                    <td className="mono hist-count-cell">{scan.configuration_drifts}</td>
                    <td className="mono hist-count-cell">{scan.runtime_changes}</td>
                    <td>
                      <div className="hist-sev-pills-row">
                        {scan.high_severity > 0 && <SeverityPill count={scan.high_severity} level="HIGH" />}
                        {scan.medium_severity > 0 && <SeverityPill count={scan.medium_severity} level="MEDIUM" />}
                        {scan.low_severity > 0 && <SeverityPill count={scan.low_severity} level="LOW" />}
                        {scan.high_severity === 0 && scan.medium_severity === 0 && scan.low_severity === 0 && (
                          <span className="mono text-muted" style={{ fontSize: '0.75rem' }}>—</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination footer */}
        {!loading && total > PAGE_SIZE && (
          <div className="hist-pagination-footer">
            <span className="mono text-muted" style={{ fontSize: '0.8125rem' }}>
              Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
            </span>
            <div className="hist-pagination-controls">
              <button className="hist-page-btn" onClick={handlePrev} disabled={page === 0}>
                <ChevronLeft size={16} /> Prev
              </button>
              <button className="hist-page-btn" onClick={handleNext} disabled={page >= totalPages - 1}>
                Next <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Scan detail drawer */}
      {selectedScanId && (
        <ScanDetailDrawer
          scanId={selectedScanId}
          onClose={() => setSelectedScanId(null)}
        />
      )}
    </div>
  );
}

// ─── Shared header sub-component ─────────────────────────────────────────────

function HistoryHeader({ onRefresh, loading, lastFetched }) {
  return (
    <div className="hist-view-header">
      <div className="hist-view-header-left">
        <div className="hist-view-icon-wrap">
          <Database size={20} className="text-blue" />
        </div>
        <div>
          <h2 className="hist-view-title">PostgreSQL Drift History</h2>
          <p className="hist-view-subtitle text-secondary">
            Persistent audit log of every infrastructure drift scan, stored in PostgreSQL.
          </p>
        </div>
      </div>
      <div className="hist-view-header-right">
        {lastFetched && (
          <span className="mono text-muted" style={{ fontSize: '0.8125rem' }}>
            <Clock size={12} /> Updated {lastFetched}
          </span>
        )}
        <button
          className={`scan-btn ${loading ? 'scanning' : ''}`}
          onClick={onRefresh}
          disabled={loading}
          title="Reload history from database"
        >
          <RefreshCw size={15} className={loading ? 'spin-icon' : ''} />
          <span>{loading ? 'Loading…' : 'Refresh History'}</span>
        </button>
      </div>
    </div>
  );
}
