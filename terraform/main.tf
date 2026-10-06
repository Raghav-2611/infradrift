# ===========================================================================
# main.tf — InfraDrift core infrastructure (EC2 drift-demo environment)
#
# What this creates:
#   1. A Security Group  — controls inbound/outbound traffic to the instance.
#   2. An EC2 Instance   — the server we will intentionally drift in later
#                          phases to demonstrate drift detection.
#
# Why EC2 for drift demos?
#   EC2 instances have rich, easily-observable attributes (instance type,
#   tags, security group rules, user-data) that can be changed outside
#   Terraform to simulate real-world configuration drift.
#
# Cost note:
#   A t3.micro instance costs ~$0.01/hr. Remember to run
#   `terraform destroy` when not in use.
# ===========================================================================

# ---------------------------------------------------------------------------
# Local values — computed once, reused throughout
# ---------------------------------------------------------------------------
locals {
  common_tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  name_prefix = "${var.project}-${var.environment}"
}

# ---------------------------------------------------------------------------
# Security Group — allows SSH (optional) and all outbound traffic
# ---------------------------------------------------------------------------
resource "aws_security_group" "drift_demo" {
  name        = "${local.name_prefix}-drift-demo-sg"
  description = "Security group for the InfraDrift drift-demo EC2 instance"

  # Outbound — allow all (instance needs to reach package repos, etc.)
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Inbound SSH — only opened when a key pair is provided.
  # Restricted to 0.0.0.0/0 as a dev convenience; tighten in staging/prod.
  dynamic "ingress" {
    for_each = var.key_pair_name != "" ? [1] : []
    content {
      description = "SSH access"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-drift-demo-sg"
  })
}

# ---------------------------------------------------------------------------
# EC2 Instance — drift-demo server
# ---------------------------------------------------------------------------
resource "aws_instance" "drift_demo" {
  ami           = var.ami_id
  instance_type = var.instance_type

  # Attach key pair only when one is provided
  key_name = var.key_pair_name != "" ? var.key_pair_name : null

  vpc_security_group_ids = [aws_security_group.drift_demo.id]

  # Minimal bootstrap: install AWS CLI so we can inspect the instance later
  user_data = <<-EOF
    #!/bin/bash
    yum update -y
    yum install -y awscli
  EOF

  # Protect against accidental termination during development
  disable_api_termination = false # set to true in prod

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-drift-demo"
  })
}
