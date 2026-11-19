# ==============================================================================
# InfraDrift Backend — Production Multi-Stage Dockerfile
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Terraform Binary Downloader
# ------------------------------------------------------------------------------
FROM debian:bookworm-slim AS terraform-installer

ARG TERRAFORM_VERSION=1.7.5
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" -o terraform.zip \
    && unzip terraform.zip \
    && mv terraform /usr/local/bin/terraform \
    && chmod +x /usr/local/bin/terraform \
    && rm terraform.zip

# ------------------------------------------------------------------------------
# Stage 2: Production Python Application Runner
# ------------------------------------------------------------------------------
FROM python:3.10-slim AS runner

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    TERRAFORM_DIR=/app/terraform

# Install runtime system packages (curl for healthchecks, git, ca-certificates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy Terraform binary from installer stage
COPY --from=terraform-installer /usr/local/bin/terraform /usr/local/bin/terraform

# Create non-root system user and group
RUN groupadd -g 10001 infradrift && \
    useradd -u 10001 -g infradrift -m -s /bin/bash infradrift

WORKDIR /app

# Copy dependency definition and install packages
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code and terraform configurations
COPY backend/app ./app
COPY terraform ./terraform

# Create directory for reconciliation plans with strict 0700 permissions
RUN mkdir -p /app/terraform/plans && \
    chown -R infradrift:infradrift /app && \
    chmod -R 750 /app && \
    chmod 700 /app/terraform/plans

# Switch to non-root user
USER infradrift

# Expose backend port
EXPOSE 8000

# Container health check against FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start Uvicorn ASGI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
