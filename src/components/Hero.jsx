import React from 'react';
import { ArrowRight, Activity } from 'lucide-react';
import { GithubIcon } from './GithubIcon';
import './Hero.css';

export function Hero() {
  return (
    <section id="overview" className="section hero-section">
      <div className="container hero-container">
        <div className="pill-label">
          <span className="pill-dot"></span>
          <span>INFRASTRUCTURE DRIFT DETECTION</span>
        </div>

        <h1 className="hero-title">
          Infrastructure. <br className="title-br" />
          <span className="hero-title-highlight">Always in Sync.</span>
        </h1>

        <p className="hero-description">
          Detect configuration drift across your cloud resources in real-time, inspect granular attribute diffs, and safely bring your infrastructure back to the desired Terraform state.
        </p>

        <div className="hero-actions">
          <a href="#live-drift" className="btn-primary">
            <Activity size={16} />
            <span>Launch Live Audit</span>
            <ArrowRight size={16} />
          </a>

          <a href="#how-it-works" className="btn-secondary">
            <span>How It Works</span>
          </a>

          <a 
            href="https://github.com" 
            target="_blank" 
            rel="noopener noreferrer" 
            className="btn-secondary"
          >
            <GithubIcon size={16} />
            <span>View on GitHub</span>
          </a>
        </div>
      </div>
    </section>
  );
}
