import React from 'react';
import { ArrowRight } from 'lucide-react';
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
          Detect configuration drift across your infrastructure and safely bring it back to the desired state.
        </p>

        <div className="hero-actions">
          <a href="#how-it-works" className="btn-primary">
            <span>Get Started</span>
            <ArrowRight size={16} />
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
