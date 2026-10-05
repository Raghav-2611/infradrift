import React from 'react';
import { Cpu, Cloud, Box, Layers } from 'lucide-react';
import './TechStack.css';

const techList = [
  { name: 'Terraform', category: 'Infrastructure as Code', icon: Cpu },
  { name: 'AWS', category: 'Cloud Provider', icon: Cloud },
  { name: 'Docker', category: 'Containerization', icon: Box },
  { name: 'Kubernetes', category: 'Orchestration', icon: Layers }
];

export function TechStack() {
  return (
    <section id="tech" className="section tech-section">
      <div className="container">
        <div className="tech-header">
          <span className="mono tech-label">SUPPORTED ECOSYSTEM</span>
          <p className="tech-subtitle">Designed to integrate seamlessly with modern cloud infrastructure tools.</p>
        </div>

        <div className="tech-grid">
          {techList.map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.name} className="tech-item">
                <div className="tech-icon-box">
                  <Icon size={18} />
                </div>
                <div className="tech-info">
                  <span className="tech-name">{item.name}</span>
                  <span className="tech-category mono">{item.category}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
