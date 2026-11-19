import React, { useState, useMemo } from 'react';
import { 
  Search, 
  ExternalLink, 
  Server, 
  CheckCircle2
} from 'lucide-react';
import './DriftTable.css';

export function DriftTable({ drifts, selectedDrift, onSelectDrift, loading }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');

  const filteredDrifts = useMemo(() => {
    if (!drifts || !Array.isArray(drifts)) return [];

    return drifts.filter((item) => {
      // Search term filter
      if (searchTerm.trim()) {
        const query = searchTerm.toLowerCase();
        const matchResName = item.resource_name?.toLowerCase().includes(query);
        const matchProp = item.property?.toLowerCase().includes(query);
        const matchType = item.resource_type?.toLowerCase().includes(query);
        const matchReason = item.reason?.toLowerCase().includes(query);
        if (!matchResName && !matchProp && !matchType && !matchReason) {
          return false;
        }
      }

      // Severity filter
      if (severityFilter !== 'ALL') {
        if (item.severity !== severityFilter) {
          return false;
        }
      }

      // Category filter
      if (categoryFilter !== 'ALL') {
        if (item.category !== categoryFilter) {
          return false;
        }
      }

      // Status filter
      if (statusFilter !== 'ALL') {
        if (item.status !== statusFilter) {
          return false;
        }
      }

      return true;
    });
  }, [drifts, searchTerm, severityFilter, categoryFilter, statusFilter]);

  const resetFilters = () => {
    setSearchTerm('');
    setSeverityFilter('ALL');
    setCategoryFilter('ALL');
    setStatusFilter('ALL');
  };

  const hasActiveFilters = searchTerm !== '' || severityFilter !== 'ALL' || categoryFilter !== 'ALL' || statusFilter !== 'ALL';

  return (
    <div className="drift-table-wrapper">
      {/* Table Toolbar & Filters */}
      <div className="table-toolbar">
        <div className="search-box">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            className="search-input mono"
            placeholder="Search resource, property, or type..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          {searchTerm && (
            <button className="clear-search-btn" onClick={() => setSearchTerm('')}>
              ×
            </button>
          )}
        </div>

        <div className="filter-controls">
          {/* Severity filter */}
          <div className="filter-group">
            <label className="filter-label mono">SEVERITY:</label>
            <select
              className="filter-select mono"
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
            >
              <option value="ALL">All Severities</option>
              <option value="HIGH">HIGH (Red)</option>
              <option value="MEDIUM">MEDIUM (Orange)</option>
              <option value="LOW">LOW (Yellow)</option>
            </select>
          </div>

          {/* Category filter */}
          <div className="filter-group">
            <label className="filter-label mono">CATEGORY:</label>
            <select
              className="filter-select mono"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="ALL">All Categories</option>
              <option value="CONFIGURATION_DRIFT">Configuration Drift</option>
              <option value="RUNTIME_STATE_CHANGE">Runtime State</option>
              <option value="DEPENDENCY_CHANGE">Dependency Change</option>
            </select>
          </div>

          {/* Status filter */}
          <div className="filter-group">
            <label className="filter-label mono">STATUS:</label>
            <select
              className="filter-select mono"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="ALL">All Statuses</option>
              <option value="DRIFTED">DRIFTED</option>
              <option value="RUNTIME_CHANGE">RUNTIME_CHANGE</option>
              <option value="DEPENDENCY_CHANGE">DEPENDENCY_CHANGE</option>
              <option value="IN_SYNC">IN_SYNC</option>
            </select>
          </div>

          {hasActiveFilters && (
            <button className="btn-reset-filters mono" onClick={resetFilters}>
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Results Count bar */}
      <div className="table-meta-bar">
        <span className="results-count mono text-secondary">
          Showing <strong>{filteredDrifts.length}</strong> of <strong>{drifts?.length ?? 0}</strong> drift records
        </span>
        <span className="table-tip text-muted">
          Click any row to open the in-depth analysis & remediation inspector.
        </span>
      </div>

      {/* Table Container */}
      <div className="table-container">
        {loading ? (
          <div className="table-loading-skeleton">
            <div className="skeleton-row"></div>
            <div className="skeleton-row"></div>
            <div className="skeleton-row"></div>
            <div className="skeleton-row"></div>
          </div>
        ) : filteredDrifts.length === 0 ? (
          <div className="table-empty-state">
            <CheckCircle2 size={36} className="text-emerald" />
            <h4 className="empty-title">No drift records found matching your criteria</h4>
            <p className="empty-subtitle text-muted">
              {hasActiveFilters 
                ? 'Try broadening your search or resetting filters above.'
                : 'Your live infrastructure matches Terraform desired state.'}
            </p>
            {hasActiveFilters && (
              <button className="btn-secondary btn-sm" onClick={resetFilters}>
                Clear All Filters
              </button>
            )}
          </div>
        ) : (
          <table className="drift-table">
            <thead>
              <tr>
                <th className="th-resource">RESOURCE NAME</th>
                <th className="th-type">RESOURCE TYPE</th>
                <th className="th-property">PROPERTY</th>
                <th className="th-desired">DESIRED VALUE</th>
                <th className="th-actual">ACTUAL VALUE</th>
                <th className="th-severity">SEVERITY</th>
                <th className="th-category">DRIFT CATEGORY</th>
                <th className="th-status">STATUS</th>
                <th className="th-action"></th>
              </tr>
            </thead>
            <tbody>
              {filteredDrifts.map((d) => {
                const isSelected = selectedDrift?.id === d.id;
                const isHigh = d.severity === 'HIGH' || d.severity === 'CRITICAL';
                const isMedium = d.severity === 'MEDIUM';

                return (
                  <tr 
                    key={d.id} 
                    className={`drift-row ${isSelected ? 'row-selected' : ''} ${isHigh ? 'severity-border-high' : ''}`}
                    onClick={() => onSelectDrift(d)}
                  >
                    {/* Resource Name */}
                    <td className="td-resource">
                      <div className="resource-cell">
                        <Server size={14} className="cell-icon text-muted" />
                        <span className="resource-name-text mono" title={d.resource_name}>
                          {d.resource_name}
                        </span>
                      </div>
                    </td>

                    {/* Resource Type */}
                    <td className="td-type">
                      <span className="type-badge mono">{d.resource_type}</span>
                    </td>

                    {/* Property */}
                    <td className="td-property">
                      <span className="property-code mono">{d.property}</span>
                    </td>

                    {/* Desired Value */}
                    <td className="td-desired">
                      <code className="val-code desired-val mono" title={d.desired_value}>
                        {d.desired_value}
                      </code>
                    </td>

                    {/* Actual Value */}
                    <td className="td-actual">
                      <code className="val-code actual-val mono" title={d.actual_value}>
                        {d.actual_value}
                      </code>
                    </td>

                    {/* Severity Indicator */}
                    <td className="td-severity">
                      <span className={`severity-pill mono ${
                        isHigh ? 'severity-high' : isMedium ? 'severity-medium' : 'severity-low'
                      }`}>
                        <span className="severity-dot"></span>
                        {d.severity}
                      </span>
                    </td>

                    {/* Drift Category */}
                    <td className="td-category">
                      <span className={`category-tag mono ${d.category}`}>
                        {d.category === 'CONFIGURATION_DRIFT' 
                          ? 'CONFIGURATION' 
                          : d.category === 'RUNTIME_STATE_CHANGE' 
                          ? 'RUNTIME' 
                          : 'DEPENDENCY'}
                      </span>
                    </td>

                    {/* Status */}
                    <td className="td-status">
                      <span className="status-label mono">{d.status}</span>
                    </td>

                    {/* Action */}
                    <td className="td-action">
                      <button 
                        className="btn-view-details mono"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectDrift(d);
                        }}
                        title="Inspect drift analysis"
                      >
                        Inspect
                        <ExternalLink size={12} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
