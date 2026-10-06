terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ---------------------------------------------------------------------------
# AWS Provider
#
# Credentials are resolved automatically at runtime — in priority order:
#   1. Environment variables  (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)
#   2. Shared credentials file (~/.aws/credentials via `aws configure`)
#   3. IAM instance role / ECS task role / SSO session
#
# NEVER hardcode credentials here or in any tracked file.
# ---------------------------------------------------------------------------
provider "aws" {
  region = var.aws_region
}
