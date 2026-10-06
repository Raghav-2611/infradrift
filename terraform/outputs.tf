# ===========================================================================
# outputs.tf — values printed after `terraform apply` and queryable via
#              `terraform output`.
# ===========================================================================

# ---------------------------------------------------------------------------
# EC2 Instance
# ---------------------------------------------------------------------------

output "instance_id" {
  description = "EC2 instance ID of the drift-demo server."
  value       = aws_instance.drift_demo.id
}

output "instance_public_ip" {
  description = "Public IPv4 address of the drift-demo EC2 instance."
  value       = aws_instance.drift_demo.public_ip
}

output "instance_public_dns" {
  description = "Public DNS hostname of the drift-demo EC2 instance."
  value       = aws_instance.drift_demo.public_dns
}

output "instance_state" {
  description = "Current power state of the EC2 instance (running | stopped | …)."
  value       = aws_instance.drift_demo.instance_state
}

output "instance_type" {
  description = "EC2 instance type (useful for drift-before snapshot)."
  value       = aws_instance.drift_demo.instance_type
}

# ---------------------------------------------------------------------------
# Security Group
# ---------------------------------------------------------------------------

output "security_group_id" {
  description = "ID of the security group attached to the drift-demo instance."
  value       = aws_security_group.drift_demo.id
}

output "security_group_name" {
  description = "Name of the security group attached to the drift-demo instance."
  value       = aws_security_group.drift_demo.name
}
