/**
 * api.js
 * FastAPI backend client for InfraDrift.
 * Endpoints:
 *   - GET /health
 *   - GET /api/drift
 *   - GET /api/history?limit=N&offset=N
 *   - GET /api/history/{scan_id}
 */

/**
 * Resolve the backend API base URL.
 * Priority order:
 *   1. VITE_API_URL environment variable (if specified at build/runtime)
 *   2. Relative path ("") for reverse proxy / same-origin routing
 */
export function getApiBaseUrl() {
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim().length > 0) {
    return envUrl.trim().replace(/\/+$/, '');
  }
  return '';
}

/**
 * Perform a request (GET or POST) with timeout and error handling.
 */
async function fetchWithTimeout(endpoint, timeoutMs = 25000, options = {}) {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${endpoint}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      method: options.method || 'GET',
      headers: {
        'Accept': 'application/json',
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers || {}),
      },
      body: options.body ? (typeof options.body === 'string' ? options.body : JSON.stringify(options.body)) : undefined,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorDetail = `HTTP ${response.status} ${response.statusText}`;
      try {
        const errJson = await response.json();
        if (errJson && errJson.detail) {
          errorDetail = errJson.detail;
        }
      } catch {
        // Not a JSON response
      }
      const err = new Error(errorDetail);
      err.status = response.status;
      throw err;
    }

    return await response.json();
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new Error(`Request to ${url} timed out after ${timeoutMs / 1000}s. Backend might be performing Terraform execution.`);
    }
    throw err;
  }
}

/**
 * Check backend liveness and connectivity.
 */
export async function checkBackendHealth() {
  try {
    const data = await fetchWithTimeout('/health', 8000);
    return {
      connected: true,
      service: data?.service || 'infradrift-backend',
      version: data?.version || '0.1.0',
      status: data?.status || 'ok',
    };
  } catch (err) {
    return {
      connected: false,
      error: err.message || 'Unable to connect to backend',
    };
  }
}

/**
 * Fetch the real-time drift detection report.
 */
export async function fetchDriftReport() {
  const rawData = await fetchWithTimeout('/api/drift', 60000);

  // Validate and normalize response structure
  const totalDrifts = Number.isInteger(rawData?.total_drifts) ? rawData.total_drifts : (rawData?.drifts?.length ?? 0);
  const configurationDrifts = Number.isInteger(rawData?.configuration_drifts) ? rawData.configuration_drifts : 0;
  const runtimeChanges = Number.isInteger(rawData?.runtime_changes) ? rawData.runtime_changes : 0;
  const status = rawData?.status || (totalDrifts > 0 ? 'DRIFT_DETECTED' : 'NO_DRIFT');
  const rawDrifts = Array.isArray(rawData?.drifts) ? rawData.drifts : [];

  const drifts = rawDrifts.map((d, index) => normalizeDriftRecord(d, index));

  // Calculate severity statistics
  const highSeverity = drifts.filter(d => d.severity === 'HIGH' || d.severity === 'CRITICAL').length;
  const mediumSeverity = drifts.filter(d => d.severity === 'MEDIUM').length;
  const lowSeverity = drifts.filter(d => d.severity === 'LOW').length;

  return {
    total_drifts: totalDrifts,
    configuration_drifts: configurationDrifts,
    runtime_changes: runtimeChanges,
    high_severity: highSeverity,
    medium_severity: mediumSeverity,
    low_severity: lowSeverity,
    status: status,
    drifts: drifts,
    scan_id: rawData?.scan_id || null,
    scanned_at: rawData?.scanned_at || null,
  };
}

/**
 * Normalize a raw drift record from the API (used for both live and historical records).
 */
function normalizeDriftRecord(d, index) {
  return {
    id: `${d.resource_name || 'res'}-${d.property || 'prop'}-${index}`,
    resource_name: d.resource_name || 'unknown_resource',
    resource_type: d.resource_type || 'unknown_type',
    property: d.property || 'unknown_property',
    desired_value: d.desired_value !== undefined && d.desired_value !== null ? String(d.desired_value) : 'null',
    actual_value: d.actual_value !== undefined && d.actual_value !== null ? String(d.actual_value) : 'null',
    severity: (d.severity || 'MEDIUM').toUpperCase(),
    status: d.status || 'DRIFTED',
    category: d.category || 'CONFIGURATION_DRIFT',
    reason: d.reason || 'Infrastructure state diverges from Terraform configuration.',
  };
}

/**
 * Fetch paginated drift scan history summaries.
 * Returns { scans, total, limit, offset } or throws.
 * If the backend returns 503 (database not configured), throws an error
 * with { isDatabaseUnavailable: true } attached.
 */
export async function fetchDriftHistory(limit = 20, offset = 0) {
  let raw;
  try {
    raw = await fetchWithTimeout(`/api/history?limit=${limit}&offset=${offset}`, 15000);
  } catch (err) {
    // Surface 503 as a special flag so the UI can show a friendly state
    if (err.message && (err.message.includes('503') || err.message.toLowerCase().includes('database') || err.message.toLowerCase().includes('not configured'))) {
      const dbErr = new Error(err.message);
      dbErr.isDatabaseUnavailable = true;
      throw dbErr;
    }
    throw err;
  }

  const scans = Array.isArray(raw?.scans) ? raw.scans.map((s) => ({
    id: s.id || '',
    scanned_at: s.scanned_at || null,
    status: s.status || 'UNKNOWN',
    total_drifts: Number.isInteger(s.total_drifts) ? s.total_drifts : 0,
    configuration_drifts: Number.isInteger(s.configuration_drifts) ? s.configuration_drifts : 0,
    runtime_changes: Number.isInteger(s.runtime_changes) ? s.runtime_changes : 0,
    high_severity: Number.isInteger(s.high_severity) ? s.high_severity : 0,
    medium_severity: Number.isInteger(s.medium_severity) ? s.medium_severity : 0,
    low_severity: Number.isInteger(s.low_severity) ? s.low_severity : 0,
  })) : [];

  return {
    scans,
    total: Number.isInteger(raw?.total_scans) ? raw.total_scans : (Number.isInteger(raw?.total) ? raw.total : scans.length),
    limit: Number.isInteger(raw?.limit) ? raw.limit : limit,
    offset: Number.isInteger(raw?.offset) ? raw.offset : offset,
  };
}

/**
 * Fetch a single historical drift scan by its UUID.
 * Returns the full scan including drift records.
 */
export async function fetchDriftScanDetail(scanId) {
  let raw;
  try {
    raw = await fetchWithTimeout(`/api/history/${scanId}`, 15000);
  } catch (err) {
    if (err.message && (err.message.includes('503') || err.message.toLowerCase().includes('database'))) {
      const dbErr = new Error(err.message);
      dbErr.isDatabaseUnavailable = true;
      throw dbErr;
    }
    throw err;
  }

  const rawDrifts = Array.isArray(raw?.drifts) ? raw.drifts : [];
  return {
    id: raw?.id || scanId,
    scanned_at: raw?.scanned_at || null,
    status: raw?.status || 'UNKNOWN',
    total_drifts: Number.isInteger(raw?.total_drifts) ? raw.total_drifts : 0,
    configuration_drifts: Number.isInteger(raw?.configuration_drifts) ? raw.configuration_drifts : 0,
    runtime_changes: Number.isInteger(raw?.runtime_changes) ? raw.runtime_changes : 0,
    high_severity: Number.isInteger(raw?.high_severity) ? raw.high_severity : 0,
    medium_severity: Number.isInteger(raw?.medium_severity) ? raw.medium_severity : 0,
    low_severity: Number.isInteger(raw?.low_severity) ? raw.low_severity : 0,
    drifts: rawDrifts.map((d, i) => normalizeDriftRecord(d, i)),
  };
}

/**
 * Generate a speculative Terraform reconciliation plan (POST /api/reconciliation/plan).
 * Read-only dry run; never executes apply or destroy.
 */
export async function generateReconciliationPlan() {
  return await fetchWithTimeout('/api/reconciliation/plan', 60000, {
    method: 'POST',
  });
}

/**
 * Fetch the latest generated reconciliation plan (GET /api/reconciliation/plan/latest).
 */
export async function fetchLatestReconciliationPlan() {
  return await fetchWithTimeout('/api/reconciliation/plan/latest', 15000);
}

/**
 * Fetch a specific reconciliation plan by UUID (GET /api/reconciliation/plan/{id}).
 */
export async function fetchReconciliationPlan(planId) {
  return await fetchWithTimeout(`/api/reconciliation/plan/${planId}`, 15000);
}

/**
 * Approve an existing PENDING_REVIEW reconciliation plan (POST /api/reconciliation/plan/{id}/approve).
 */
export async function approveReconciliationPlan(planId, payload = { approved_by: 'admin', comment: '' }) {
  return await fetchWithTimeout(`/api/reconciliation/plan/${planId}/approve`, 20000, {
    method: 'POST',
    body: payload,
  });
}

/**
 * Reject an existing reconciliation plan (POST /api/reconciliation/plan/{id}/reject).
 */
export async function rejectReconciliationPlan(planId, payload = { rejected_by: 'admin', reason: 'Rejected by operator' }) {
  return await fetchWithTimeout(`/api/reconciliation/plan/${planId}/reject`, 20000, {
    method: 'POST',
    body: payload,
  });
}

/**
 * Validate execution readiness of a reconciliation plan (GET /api/reconciliation/plan/{id}/readiness).
 */
export async function fetchExecutionReadiness(planId) {
  return await fetchWithTimeout(`/api/reconciliation/plan/${planId}/readiness`, 15000);
}
