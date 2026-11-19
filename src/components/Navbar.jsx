import React, { useState } from 'react';
import { Terminal, Menu, X } from 'lucide-react';
import { GithubIcon } from './GithubIcon';
import './Navbar.css';

export function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleNavClick = (hash) => {
    setMobileMenuOpen(false);
    window.location.hash = hash;
    // Smooth scroll to drift dashboard if it's a dashboard tab
    if (['#live-drift', '#recommendations', '#reconciliation', '#history'].includes(hash)) {
      const element = document.getElementById('live-drift');
      if (element) {
        element.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  return (
    <header className="navbar-header">
      <div className="container navbar-container">
        <a href="#overview" className="navbar-brand">
          <div className="brand-icon">
            <Terminal size={18} />
          </div>
          <span className="brand-name">InfraDrift</span>
          <span className="brand-badge">v0.1.0-live</span>
        </a>

        {/* Desktop Navigation */}
        <nav className="navbar-nav desktop-nav">
          <a href="#overview" className="nav-link" onClick={() => handleNavClick('#overview')}>
            Overview
          </a>
          <a href="#live-drift" className="nav-link" onClick={() => handleNavClick('#live-drift')}>
            Drift Detection
          </a>
          <a href="#recommendations" className="nav-link" onClick={() => handleNavClick('#recommendations')}>
            Recommendations
          </a>
          <a href="#reconciliation" className="nav-link" onClick={() => handleNavClick('#reconciliation')}>
            Reconciliation
          </a>
          <a href="#history" className="nav-link" onClick={() => handleNavClick('#history')}>
            History
          </a>
          <a href="#how-it-works" className="nav-link" onClick={() => handleNavClick('#how-it-works')}>
            Pipeline
          </a>
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

        {/* Mobile Hamburger Toggle */}
        <button 
          className="mobile-menu-toggle"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle navigation menu"
        >
          {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile Dropdown Menu */}
      {mobileMenuOpen && (
        <div className="mobile-dropdown-menu">
          <a href="#overview" className="mobile-nav-link" onClick={() => handleNavClick('#overview')}>
            Overview
          </a>
          <a href="#live-drift" className="mobile-nav-link" onClick={() => handleNavClick('#live-drift')}>
            Drift Detection
          </a>
          <a href="#recommendations" className="mobile-nav-link" onClick={() => handleNavClick('#recommendations')}>
            Recommendations
          </a>
          <a href="#reconciliation" className="mobile-nav-link" onClick={() => handleNavClick('#reconciliation')}>
            Reconciliation
          </a>
          <a href="#history" className="mobile-nav-link" onClick={() => handleNavClick('#history')}>
            Drift History
          </a>
          <a href="#how-it-works" className="mobile-nav-link" onClick={() => handleNavClick('#how-it-works')}>
            How It Works
          </a>
          <a 
            href="https://github.com" 
            target="_blank" 
            rel="noopener noreferrer" 
            className="mobile-nav-link github-mobile-link"
          >
            <GithubIcon size={16} />
            <span>View on GitHub</span>
          </a>
        </div>
      )}
    </header>
  );
}
