# InfraDrift — Backend

Python + FastAPI backend that detects infrastructure drift by running a Terraform refresh-only plan and comparing desired vs actual AWS state.

---

## Architecture

```
backend/
├── app/
│   ├── main.py                    # FastAPI app, routes: /health  /api/drift
│   ├── services/
│   │   ├── terraform_service.py   # Runs terraform plan/show subprocesses
│   │   ├── aws_service.py         # Optional boto3 live-AWS cross-check
│   │   └── drift_engine.py        # Pure analysis: parses plan JSON → drift records
│   └── models/
│       └── drift.py               # Pydantic models: DriftRecord, DriftReport
├── requirements.txt
└── README.md
```

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | ≥ 3.11 | `python3 --version` |
| Terraform | ≥ 1.6 | Must be on `$PATH` |
| AWS credentials | — | env vars or `~/.aws/credentials` or IAM role |

---

## Local setup

```bash
# From the project root
cd backend

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Start the backend

```bash
# Run from the project root so the terraform/ directory is resolvable
cd /path/to/infradrift

uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

The `--reload` flag restarts the server automatically when source files change (dev only).

---

## API endpoints

### `GET /health`

Liveness check — confirms the backend process is running.

```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "ok",
  "service": "infradrift-backend",
  "version": "0.1.0"
}
```

---

### `GET /api/drift`

Runs a Terraform refresh-only plan and returns a structured drift report.

```bash
curl http://localhost:8000/api/drift
```

**Response when drift is detected:**
```json
{
  "total_drifts": 1,
  "status": "DRIFT_DETECTED",
  "drifts": [
    {
      "resource_name": "aws_instance.drift_demo",
      "resource_type": "aws_instance",
      "property": "instance_type",
      "desired_value": "t3.small",
      "actual_value": "t3.micro",
      "severity": "HIGH",
      "status": "DRIFTED"
    }
  ]
}
```

**Response when no drift:**
```json
{
  "total_drifts": 0,
  "status": "NO_DRIFT",
  "drifts": []
}
```

> ⚠️ This endpoint **only** runs `terraform plan -refresh-only`. It never calls `terraform apply` and never modifies infrastructure.

---

## Interactive API docs

FastAPI generates Swagger UI automatically:

```
http://localhost:8000/docs
```

ReDoc alternative:

```
http://localhost:8000/redoc
```

---

## Severity classification

| Severity | Example properties |
|----------|--------------------|
| `CRITICAL` | `deletion_protection`, `disable_api_termination` |
| `HIGH` | `instance_type`, `ami`, `vpc_security_group_ids`, `subnet_id` |
| `MEDIUM` | All other attributes |
| `LOW` | `tags`, `tags_all`, `volume_tags` |

---

## Error responses

| HTTP code | Cause |
|-----------|-------|
| `500` | Terraform not installed, terraform/ dir missing, or plan command failed |
| `504` | Terraform plan timed out (> 120 s) — check AWS connectivity |
