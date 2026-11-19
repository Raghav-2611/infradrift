/**
 * api.js
 * FastAPI backend client for InfraDrift.
 * Endpoints:
 *   - GET /health
 *   - GET /api/drift
 */

const DEFAULT_BACKEND_URL = 'http://3.90.25.185:8000';

export function getApiBaseUrl() {
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim().length > 0) {
    return envUrl.trim().replace(/\/+$/, '');
  }
  return DEFAULT_BACKEND_URL;
}

/**
 * Perform a GET request with timeout and error handling.
 */
async function fetchWithTimeout(endpoint, timeoutMs = 25000) {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${endpoint}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
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
      throw new Error(errorDetail);
    }

    return await response.json();
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new Error(`Request to ${url} timed out after ${timeoutMs / 1000}s. Backend might be performing Terraform refresh.`);
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

  const drifts = rawDrifts.map((d, index) => ({
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
  }));

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
  };
}
