import React from 'react';
import { 
  Database, 
  GitMerge, 
  BarChart3, 
  Lock 
} from 'lucide-react';
import './FutureModules.css';

export function FutureHistoryModule() {
  return (
    <div className="future-module-card">
      <div className="module-banner-header">
        <div className="module-icon-wrap bg-blue-subtle">
          <Database size={24} className="text-blue" />
        </div>
        <div className="module-title-wrap">
          <div className="module-tag-row">
            <span className="module-status-badge pending mono">NOT YET CONNECTED</span>
            <span className="module-subtag mono">MODULE: INFRA-STORE-PG</span>
          </div>
          <h3 className="module-heading">PostgreSQL Drift History & Audit Logs</h3>
          <p className="module-desc text-secondary">
            Continuous temporal persistence tracking infrastructure state variations, drift lifespans, and automated snapshots across AWS account boundaries.
          </p>
        </div>
      </div>

      <div className="module-body-grid">
        <div className="module-spec-card">
          <h4 className="spec-title mono text-primary">PLANNED CAPABILITIES</h4>
          <ul className="spec-list text-secondary">
            <li>Historical diff comparison across any arbitrary point-in-time</li>
            <li>Mean-Time-To-Detect (MTTD) & Mean-Time-To-Remediate (MTTR) metrics</li>
            <li>Automated drift attribution via AWS CloudTrail event ingestion</li>
            <li>Audit compliance exports (CSV, JSON, SOC2 Type II reports)</li>
          </ul>
        </div>

        <div className="module-spec-card">
          <h4 className="spec-title mono text-primary">DATABASE SCHEMA DESIGN</h4>
          <div className="code-blueprint mono text-muted">
            <span className="code-comment">-- Target PostgreSQL Migration 002</span><br/>
            <span className="code-keyword">CREATE TABLE</span> drift_history (<br/>
            &nbsp;&nbsp;id <span className="code-type">UUID PRIMARY KEY DEFAULT gen_random_uuid()</span>,<br/>
            &nbsp;&nbsp;resource_arn <span className="code-type">TEXT NOT NULL</span>,<br/>
            &nbsp;&nbsp;property <span className="code-type">VARCHAR(64) NOT NULL</span>,<br/>
            &nbsp;&nbsp;desired_state <span className="code-type">JSONB NOT NULL</span>,<br/>
            &nbsp;&nbsp;actual_state <span className="code-type">JSONB NOT NULL</span>,<br/>
            &nbsp;&nbsp;severity <span className="code-type">VARCHAR(16) NOT NULL</span>,<br/>
            &nbsp;&nbsp;detected_at <span className="code-type">TIMESTAMPTZ DEFAULT NOW()</span>,<br/>
            &nbsp;&nbsp;reconciled_at <span className="code-type">TIMESTAMPTZ NULL</span><br/>
            );
          </div>
        </div>
      </div>

      <div className="module-footer-status">
        <div className="status-connection-row">
          <span className="status-dot dot-pending"></span>
          <span className="status-conn-text mono">Backend Integration Status: Pending Database Migration</span>
        </div>
        <span className="status-action-hint mono text-muted">Awaiting backend endpoint: GET /api/v1/history</span>
      </div>
    </div>
  );
}

export function FutureReconciliationModule() {
  return (
    <div className="future-module-card">
      <div className="module-banner-header">
        <div className="module-icon-wrap bg-amber-subtle">
          <GitMerge size={24} className="text-amber" />
        </div>
        <div className="module-title-wrap">
          <div className="module-tag-row">
            <span className="module-status-badge pending mono">READ-ONLY SAFEGUARD ACTIVE</span>
            <span className="module-subtag mono">MODULE: RECONCILE-PIPELINE</span>
          </div>
          <h3 className="module-heading">Safe Reconciliation & Terraform Apply Guardrails</h3>
          <p className="module-desc text-secondary">
            Safely realign drifted infrastructure with two-factor approval checkpoints before running <code>terraform apply</code>. Zero risk of accidental resource destruction.
          </p>
        </div>
      </div>

      {/* Visual Workflow Steps */}
      <div className="reconcile-pipeline-flow">
        <div className="flow-step">
          <div className="step-num-pill mono">1</div>
          <div className="step-title mono">Speculative Plan</div>
          <div className="step-desc text-muted">Generate targeted dry-run execution graph</div>
        </div>
        <div className="flow-connector mono">→</div>
        <div className="flow-step">
          <div className="step-num-pill mono">2</div>
          <div className="step-title mono">Dual Approval</div>
          <div className="step-desc text-muted">Requires peer review before mutation</div>
        </div>
        <div className="flow-connector mono">→</div>
        <div className="flow-step">
          <div className="step-num-pill mono">3</div>
          <div className="step-title mono">Isolated Apply</div>
          <div className="step-desc text-muted">Targeted apply targeting drifted resources only</div>
        </div>
        <div className="flow-connector mono">→</div>
        <div className="flow-step">
          <div className="step-num-pill mono">4</div>
          <div className="step-title mono">Post-Verification</div>
          <div className="step-desc text-muted">Automated re-scan confirming 0 drift remaining</div>
        </div>
      </div>

      <div className="module-body-grid">
        <div className="module-spec-card">
          <h4 className="spec-title mono text-primary">RECONCILIATION EXECUTION STATUS</h4>
          <div className="reconcile-safety-box">
            <Lock size={18} className="text-amber" />
            <div>
              <div className="safety-title mono font-semibold">Production Mutation Lock Enabled</div>
              <p className="safety-desc text-secondary">
                The FastAPI backend is currently operating in <strong>Detection-Only Mode</strong> (executing <code>terraform plan -refresh-only</code>). Mutating <code>terraform apply</code> actions are strictly disabled until safe reconciliation gates are configured.
              </p>
            </div>
          </div>
        </div>

        <div className="module-spec-card">
          <h4 className="spec-title mono text-primary">POST-RECONCILIATION VERIFICATION</h4>
          <p className="verification-text text-secondary">
            Once safe reconciliation is enabled, each apply cycle will trigger an immediate, non-cached AWS state query to verify that desired values (e.g. <code>t3.small</code>) have successfully propagated into live AWS EC2 metadata.
          </p>
          <div className="endpoint-preview mono text-muted">
            Target API: POST /api/reconcile/plan &bull; POST /api/reconcile/apply
          </div>
        </div>
      </div>

      <div className="module-footer-status">
        <div className="status-connection-row">
          <span className="status-dot dot-pending"></span>
          <span className="status-conn-text mono">Backend Integration Status: Safe Guard Active (Apply API Not Exposed)</span>
        </div>
        <span className="status-action-hint mono text-muted">Safe by design: No automatic AWS mutations</span>
      </div>
    </div>
  );
}

export function FutureMonitoringModule() {
  return (
    <div className="future-module-card">
      <div className="module-banner-header">
        <div className="module-icon-wrap bg-emerald-subtle">
          <BarChart3 size={24} className="text-emerald" />
        </div>
        <div className="module-title-wrap">
          <div className="module-tag-row">
            <span className="module-status-badge pending mono">COMING SOON</span>
            <span className="module-subtag mono">MODULE: OBSERVABILITY</span>
          </div>
          <h3 className="module-heading">Prometheus Metrics & Grafana Dashboard Integration</h3>
          <p className="module-desc text-secondary">
            Real-time infrastructure drift telemetry exposed via Prometheus standard metrics exporter and visualizable on enterprise Grafana dashboards.
          </p>
        </div>
      </div>

      <div className="module-body-grid">
        <div className="module-spec-card">
          <h4 className="spec-title mono text-primary">PLANNED PROMETHEUS METRICS</h4>
          <div className="code-blueprint mono text-muted">
            <span className="code-comment"># TYPE infradrift_drifts_total gauge</span><br/>
            infradrift_drifts_total&#123;severity="HIGH",category="CONFIG"&#125; 1<br/>
            infradrift_drifts_total&#123;severity="LOW",category="RUNTIME"&#125; 3<br/>
            <span className="code-comment"># TYPE infradrift_scan_duration_seconds histogram</span><br/>
            infradrift_scan_duration_seconds_bucket&#123;le="5"&#125; 0<br/>
            infradrift_scan_duration_seconds_bucket&#123;le="15"&#125; 1<br/>
            <span className="code-comment"># TYPE infradrift_last_scan_timestamp gauge</span><br/>
            infradrift_last_scan_timestamp 1731974400
          </div>
        </div>

        <div className="module-spec-card">
          <h4 className="spec-title mono text-primary">GRAFANA DASHBOARD SUITE</h4>
          <ul className="spec-list text-secondary">
            <li>Pre-baked Grafana dashboard JSON models for AWS & Cloud infrastructure monitoring</li>
            <li>Alertmanager routing for Slack, PagerDuty, and OpsGenie on HIGH-severity drift</li>
            <li>Trend graphs showing drift velocity over deployment sprints</li>
          </ul>
        </div>
      </div>

      <div className="module-footer-status">
        <div className="status-connection-row">
          <span className="status-dot dot-pending"></span>
          <span className="status-conn-text mono">Backend Integration Status: Exporter Pipeline in Development</span>
        </div>
        <span className="status-action-hint mono text-muted">Awaiting endpoint: GET /metrics</span>
      </div>
    </div>
  );
}
