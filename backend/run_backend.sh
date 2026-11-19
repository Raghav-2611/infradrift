#!/usr/bin/env bash
# ==============================================================================
# InfraDrift Backend Startup Script
# Safely loads backend/.env.runtime and starts Uvicorn
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Activate virtual environment if present
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "../.venv/bin/activate" ]; then
    source ../.venv/bin/activate
fi

# 2. Export environment variables from .env.runtime
# 'set -a' exports all variables to subprocesses
if [ -f ".env.runtime" ]; then
    set -a
    # shellcheck disable=SC1091
    source .env.runtime
    set +a
    echo "[InfraDrift] Exported runtime environment from .env.runtime"
elif [ -f "../.env.runtime" ]; then
    set -a
    # shellcheck disable=SC1091
    source ../.env.runtime
    set +a
    echo "[InfraDrift] Exported runtime environment from ../.env.runtime"
fi

# 3. Environment defaults
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export PORT="${PORT:-8000}"

# 4. Start Uvicorn ASGI server
echo "[InfraDrift] Starting FastAPI backend on 0.0.0.0:${PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"
