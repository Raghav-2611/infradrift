import React from 'react';
import { Navbar } from './components/Navbar';
import { Hero } from './components/Hero';
import { VisualPipeline } from './components/VisualPipeline';
import { HowItWorks } from './components/HowItWorks';
import { TechStack } from './components/TechStack';
import { Footer } from './components/Footer';

export default function App() {
  return (
    <div className="app-root">
      <div className="bg-grid"></div>
      <Navbar />
      <main>
        <Hero />
        <VisualPipeline />
        <HowItWorks />
        <TechStack />
      </main>
      <Footer />
    </div>
  );
}
