# InfraDrift

> Infrastructure. Always in Sync.

InfraDrift is an automated platform designed to detect differences between the desired state and actual state of cloud infrastructure and help safely bring infrastructure back into sync.

This repository contains **Phase 1** of InfraDrift: a minimalist, high-performance landing page built with React and Vite.

---

## 🚀 Getting Started

### Prerequisites
Make sure you have Node.js (v18 or higher) and `npm` installed.

### 1. Install Dependencies
```bash
npm install
```

### 2. Start Development Server
Run the Vite development server locally:
```bash
npm run dev
```

The application will start at `http://localhost:5173` (or the next available port).

### 3. Build for Production
To generate a production-ready build:
```bash
npm run build
```

To preview the production build locally:
```bash
npm run preview
```

---

## 🛠️ Project Architecture

```
infradrift/
├── index.html              # HTML entry point with Google Fonts & SEO tags
├── package.json            # Dependencies and npm scripts
├── vite.config.js          # Vite configuration
└── src/
    ├── main.jsx            # React root mount
    ├── App.jsx             # Main landing page layout
    ├── index.css           # Minimalist design tokens & global CSS
    └── components/
        ├── Navbar.jsx      # Top navigation header
        ├── Hero.jsx        # Hero section with primary CTA
        ├── VisualPipeline.jsx # Interactive 4-step pipeline representation
        ├── HowItWorks.jsx  # 01 Define, 02 Detect, 03 Reconcile steps
        ├── TechStack.jsx   # Terraform, AWS, Docker, Kubernetes ecosystem badges
        └── Footer.jsx      # Clean minimal footer & links
```

---

## 🎨 Design Principles

- **Minimalist Aesthetic:** Dark theme with subtle slate borders, monochrome foundation, and generous whitespace.
- **Developer First:** Monospace typography details, crisp terminal code preview, and high-contrast UI.
- **Zero Bloat:** Lightweight React components with zero unnecessary third-party overhead.
