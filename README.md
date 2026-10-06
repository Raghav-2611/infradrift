# InfraDrift

> Infrastructure. Always in Sync.

InfraDrift is an automated platform designed to detect differences between the desired state and actual state of cloud infrastructure and help safely bring infrastructure back into sync.

---

## 📦 Phase 2 — Docker (Current)

The InfraDrift frontend is fully containerised using a multi-stage Docker build:

- **Stage 1 (builder):** `node:22-alpine` — installs dependencies and produces the Vite production bundle.
- **Stage 2 (runner):** `nginx:1.27-alpine` — serves the static bundle with a lightweight, security-hardened Nginx config.

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

### Build the Docker Image

```bash
docker build -t infradrift:latest .
```

### Run the Docker Container

```bash
docker run -d -p 8080:80 --name infradrift infradrift:latest
```

| Flag | Purpose |
|------|---------|
| `-d` | Run in detached (background) mode |
| `-p 8080:80` | Map host port **8080** → container port **80** |
| `--name infradrift` | Give the container a friendly name |

### Open in Browser

```
http://localhost:8080
```

### Stop & Remove the Container

```bash
docker stop infradrift && docker rm infradrift
```

---

## 🚀 Phase 1 — Local Development

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
├── Dockerfile              # Multi-stage Docker build (Phase 2)
├── .dockerignore           # Docker build context exclusions
├── nginx.conf              # Nginx SPA routing config (Phase 2)
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
