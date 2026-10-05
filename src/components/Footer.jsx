import React from 'react';
import { Terminal } from 'lucide-react';
import { GithubIcon } from './GithubIcon';
import './Footer.css';

export function Footer() {
  return (
    <footer className="footer-section">
      <div className="container footer-container">
        <div className="footer-brand">
          <div className="footer-brand-title">
            <div className="footer-icon">
              <Terminal size={16} />
            </div>
            <span className="footer-name">InfraDrift</span>
          </div>
          <p className="footer-tagline text-secondary">
            Automated Infrastructure Drift Detection & Safe Reconciliation
          </p>
        </div>

        <div className="footer-links">
          <a 
            href="https://github.com" 
            target="_blank" 
            rel="noopener noreferrer" 
            className="footer-github-link"
          >
            <GithubIcon size={16} />
            <span>GitHub Repository</span>
          </a>
        </div>
      </div>

      <div className="container footer-bottom">
        <span className="mono footer-copy">
          &copy; {new Date().getFullYear()} InfraDrift Project. Minimalist DevOps Platform.
        </span>
      </div>
    </footer>
  );
}
