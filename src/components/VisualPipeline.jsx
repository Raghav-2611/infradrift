import React, { useState } from 'react';
import { FileCode, Cloud, AlertTriangle, CheckCircle2, ArrowRight } from 'lucide-react';
import './VisualPipeline.css';

const stepsData = [
  {
    id: 'desired',
    stepNumber: '01',
    title: 'Desired State',
    subtitle: 'Declarative Code',
    icon: FileCode,
    status: 'neutral',
    codeSnippet: `# main.tf (Git repo)
resource "aws_security_group" "web" {
  name        = "web-secgroup"
  ingress_port = 443
  ssl_policy   = "TLS-1-3"
}`
  },
  {
    id: 'actual',
    stepNumber: '02',
    title: 'Actual State',
    subtitle: 'Live Cloud Infra',
    icon: Cloud,
    status: 'neutral',
    codeSnippet: `# AWS Cloud Runtime API
resource "aws_security_group" "web" {
  name        = "web-secgroup"
  ingress_port = 80   # Changed manually!
  ssl_policy   = "TLS-1-0"
}`
  },
  {
    id: 'drift',
    stepNumber: '03',
    title: 'Drift Detected',
    subtitle: 'State Mismatch',
    icon: AlertTriangle,
    status: 'warning',
    codeSnippet: `! DRIFT DISCOVERED
- ingress_port: 443 (Desired) != 80 (Actual)
- ssl_policy:   TLS-1-3 (Desired) != TLS-1-0 (Actual)
[ALERT] Unapproved change in us-east-1`
  },
  {
    id: 'reconciled',
    stepNumber: '04',
    title: 'Reconciled',
    subtitle: 'In Sync',
    icon: CheckCircle2,
    status: 'success',
    codeSnippet: `✓ RECONCILIATION COMPLETE
+ Applied plan #dr-9402
+ Restored ingress_port -> 443
+ Enforced ssl_policy -> TLS-1-3
Status: 100% In Sync`
  }
];

export function VisualPipeline() {
  const [activeStep, setActiveStep] = useState(2); // Default to step 3 (drift) for visual interest

  return (
    <section className="section visual-section">
      <div className="container">
        <div className="visual-header">
          <span className="mono visual-subtitle">REAL-TIME PIPELINE</span>
          <h2 className="visual-title">Continuous Reconciliation Flow</h2>
        </div>

        {/* Minimal Pipeline Nodes */}
        <div className="pipeline-grid">
          {stepsData.map((step, index) => {
            const Icon = step.icon;
            const isActive = activeStep === index;
            const isLast = index === stepsData.length - 1;

            return (
              <React.Fragment key={step.id}>
                <div 
                  className={`pipeline-card ${isActive ? 'active' : ''} ${step.status}`}
                  onClick={() => setActiveStep(index)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === 'Enter' && setActiveStep(index)}
                >
                  <div className="card-top">
                    <span className="step-num mono">{step.stepNumber}</span>
                    <div className={`status-indicator ${step.status}`}>
                      <Icon size={16} />
                    </div>
                  </div>
                  <h3 className="card-title">{step.title}</h3>
                  <p className="card-subtitle mono">{step.subtitle}</p>
                </div>

                {!isLast && (
                  <div className="pipeline-connector">
                    <div className="connector-line"></div>
                    <ArrowRight size={14} className="connector-arrow" />
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>

        {/* Live Code/Diff Terminal View */}
        <div className="terminal-window">
          <div className="terminal-header">
            <div className="terminal-dots">
              <span className="dot red"></span>
              <span className="dot yellow"></span>
              <span className="dot green"></span>
            </div>
            <div className="terminal-title mono">
              infradrift inspect --step={stepsData[activeStep].id}
            </div>
            <div className="terminal-badge mono">
              {stepsData[activeStep].title}
            </div>
          </div>
          <div className="terminal-body mono">
            <pre>{stepsData[activeStep].codeSnippet}</pre>
          </div>
        </div>
      </div>
    </section>
  );
}
