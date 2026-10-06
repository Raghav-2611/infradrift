# InfraDrift — Terraform

This directory contains the Terraform configuration that manages all AWS infrastructure for InfraDrift as code.

---

## What Terraform manages

| Resource | Type | Purpose |
|----------|------|---------|
| `aws_security_group.drift_demo` | Security Group | Controls traffic to the EC2 instance |
| `aws_instance.drift_demo` | EC2 | Drift-demo server — the target for future drift detection phases |

The EC2 instance is intentionally minimal. In later phases its attributes (instance type, tags, security group rules) will be mutated outside of Terraform to simulate real-world infrastructure drift, which InfraDrift will detect and report.

---

## Prerequisites

| Tool | Minimum version | Install |
|------|----------------|---------|
| Terraform | 1.6.0 | [terraform.io/downloads](https://developer.hashicorp.com/terraform/install) |
| AWS CLI | any | [aws.amazon.com/cli](https://aws.amazon.com/cli/) |
| AWS credentials | — | `aws configure` or env vars |

### Authenticating to AWS

Terraform picks up credentials automatically — **never hardcode them**:

```bash
# Option A — AWS CLI profile (recommended for local dev)
aws configure

# Option B — Environment variables
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="us-east-1"
```

---

## Quick start

```bash
# 1. Copy the example vars and fill in your values
cp terraform.tfvars.example terraform.tfvars

# 2. Initialise Terraform (downloads the AWS provider)
terraform init

# 3. Validate — checks syntax without contacting AWS
terraform validate

# 4. Preview — shows exactly what will be created (no changes made)
terraform plan

# 5. Apply — creates real AWS resources (only when you are ready)
# terraform apply
```

> ⚠️  **Do NOT run `terraform apply` automatically.** Always review the plan first.

---

## Destroying resources

```bash
terraform destroy
```

Remember to run this when the drift-demo environment is no longer needed to avoid unnecessary AWS charges (~$0.01/hr for t3.micro).

---

## File reference

| File | Purpose |
|------|---------|
| `providers.tf` | AWS provider declaration and version constraints |
| `variables.tf` | All input variables (region, project, env, instance type, AMI, key pair) |
| `main.tf` | Resource definitions — Security Group and EC2 instance |
| `outputs.tf` | Exported values: instance ID, public IP, DNS, state, SG ID |
| `terraform.tfvars.example` | Template to copy → `terraform.tfvars` (git-ignored) |
| `.terraform.lock.hcl` | Provider lock file — **committed to version control** |

---

## Security notes

- `terraform.tfvars` is git-ignored — never commit real credentials or account IDs.
- `.terraform/` is git-ignored — contains local provider binaries.
- `*.tfstate` is git-ignored — state files may contain sensitive resource metadata.
- `.terraform.lock.hcl` **is committed** — ensures everyone uses the same provider version.
