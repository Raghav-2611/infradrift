# ===========================================================================
# variables.tf — all configurable inputs for the InfraDrift infrastructure.
#
# Values are supplied via terraform.tfvars (git-ignored) or -var flags.
# The .example file is committed so any team member can onboard quickly.
# ===========================================================================

# ---------------------------------------------------------------------------
# Global
# ---------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region where all resources will be provisioned."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project name — used as a prefix and tag on every resource."
  type        = string
  default     = "infradrift"
}

variable "environment" {
  description = "Deployment environment label (dev | staging | prod)."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

# ---------------------------------------------------------------------------
# EC2 — Drift-demo instance
# ---------------------------------------------------------------------------

variable "instance_type" {
  description = "EC2 instance type for the drift-demo server."
  type        = string
  default     = "t3.small"
}

variable "ami_id" {
  description = <<-EOT
    AMI ID to launch on the EC2 instance.
    Defaults to the latest Amazon Linux 2023 AMI in us-east-1.
    If you change the region, update this value accordingly.

    Find the latest AMI for your region:
      aws ec2 describe-images \
        --owners amazon \
        --filters "Name=name,Values=al2023-ami-*-x86_64" \
        --query "sort_by(Images, &CreationDate)[-1].ImageId" \
        --output text
  EOT
  type        = string
  default     = "ami-0c02fb55956c7d316" # Amazon Linux 2023 — us-east-1
}

variable "key_pair_name" {
  description = <<-EOT
    Name of an existing EC2 key pair to attach to the instance for SSH access.
    Leave empty ("") to launch without a key pair (no SSH, SSM only).
  EOT
  type        = string
  default     = ""
}
