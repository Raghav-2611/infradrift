import React from 'react';
import { Terminal } from 'lucide-react';
import { GithubIcon } from './GithubIcon';
import './Navbar.css';

export function Navbar() {
  return (
    <header className="navbar-header">
      <div className="container navbar-container">
        <a href="#" className="navbar-brand">
          <div className="brand-icon">
            <Terminal size={18} />
          </div>
          <span className="brand-name">InfraDrift</span>
          <span className="brand-badge">alpha</span>
        </a>

        <nav className="navbar-nav">
          <a href="#overview" className="nav-link">Overview</a>
          <a href="#live-drift" className="nav-link">Live Audit</a>
          <a href="#how-it-works" className="nav-link">How It Works</a>
          <a href="#tech" className="nav-link">Tech</a>
          <a 
            href="https://github.com" 
            target="_blank" 
            rel="noopener noreferrer" 
            className="nav-link github-link"
          >
            <GithubIcon size={16} />
            <span>GitHub</span>
          </a>
        </nav>
      </div>
    </header>
  );
}
