# ─────────────────────────────────────────────
# Stage 1 — Build
# ─────────────────────────────────────────────
FROM node:22-alpine AS builder

# Set working directory
WORKDIR /app

# Copy dependency manifests first (layer-cache optimization)
COPY package.json package-lock.json ./

# Install dependencies (ci for reproducible installs)
RUN npm ci

# Copy the rest of the source
COPY . .

# Build the production bundle
RUN npm run build

# ─────────────────────────────────────────────
# Stage 2 — Serve
# ─────────────────────────────────────────────
FROM nginx:1.27-alpine AS runner

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom nginx config for SPA routing support
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start nginx in the foreground
CMD ["nginx", "-g", "daemon off;"]
