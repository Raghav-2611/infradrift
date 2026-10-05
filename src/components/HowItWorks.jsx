import React from 'react';
import { Sliders, Search, ShieldCheck } from 'lucide-react';
import './HowItWorks.css';

const steps = [
  {
    number: '01',
    title: 'Define',
    description: 'Define your desired infrastructure state.',
    icon: Sliders,
    detail: 'Use declarative standard formats like Terraform code or GitOps manifests as your single source of truth.'
  },
  {
    number: '02',
    title: 'Detect',
    description: 'Compare your desired state with the actual infrastructure.',
    icon: Search,
    detail: 'Continuous continuous monitoring compares deployed cloud resources against git commits in real-time.'
  },
  {
    number: '03',
    title: 'Reconcile',
    description: 'Safely bring detected drift back into sync.',
    icon: ShieldCheck,
    detail: 'Automated policy-driven workflows restore unapproved changes without risking cloud outages.'
  }
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="section how-section">
      <div className="container">
        <div className="how-header">
          <div className="pill-label">
            <span className="pill-dot"></span>
            <span>WORKFLOW</span>
          </div>
          <h2 className="how-title">How It Works</h2>
          <p className="how-subtitle">
            Three simple steps to guarantee zero configuration drift across cloud environments.
          </p>
        </div>

        <div className="steps-grid">
          {steps.map((step) => {
            const Icon = step.icon;
            return (
              <div key={step.number} className="step-card">
                <div className="step-header">
                  <span className="step-number mono">{step.number}</span>
                  <div className="step-icon-wrapper">
                    <Icon size={18} />
                  </div>
                </div>
                <h3 className="step-title">{step.title}</h3>
                <p className="step-description">{step.description}</p>
                <p className="step-detail text-muted">{step.detail}</p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
