/**
 * driftAnalysis.js
 * Generates technical DevOps analysis, potential impact evaluations,
 * and actionable corrective recommendations for detected drifts.
 */

/**
 * Evaluates the potential technical and operational impact of a detected drift.
 */
export function getDriftImpact(drift) {
  const prop = drift.property?.toLowerCase();
  const isConfig = drift.category === 'CONFIGURATION_DRIFT';

  if (prop === 'instance_type') {
    return {
      riskLevel: 'HIGH',
      summary: 'Compute & Memory Sizing Mismatch',
      description: `EC2 instance size drifted from desired '${drift.desired_value}' to live '${drift.actual_value}'. If running a smaller tier (e.g. t3.micro instead of t3.small), RAM is reduced by 50% (from 2 GiB to 1 GiB), leading to high risk of Linux OOM-killer terminating critical processes, CPU credit exhaustion under sustained traffic, and degraded I/O throughput.`,
      costImpact: 'May alter AWS hourly On-Demand/Reserved EC2 billing rates.',
      complianceImpact: 'Violates Infrastructure-as-Code parity and change-freeze policies.',
    };
  }

  if (prop === 'ami') {
    return {
      riskLevel: 'CRITICAL',
      summary: 'Base OS Image Divergence',
      description: `Instance is running an unapproved AMI (${drift.actual_value}) instead of the declared base image (${drift.desired_value}). May introduce untested kernel revisions, missing security agents, or outdated vulnerability patches.`,
      costImpact: 'Neutral',
      complianceImpact: 'Severe compliance failure for SOC2/ISO27001 base-image requirements.',
    };
  }

  if (prop === 'security_groups' || prop === 'vpc_security_group_ids') {
    return {
      riskLevel: 'CRITICAL',
      summary: 'Network Security Boundary Drift',
      description: `Security group rules diverge from Terraform desired configuration. Could expose internal services to unintended CIDR blocks or sever required intra-VPC peering.`,
      costImpact: 'Neutral',
      complianceImpact: 'High risk of network perimeter breach or firewall audit failure.',
    };
  }

  if (prop === 'ebs_optimized') {
    return {
      riskLevel: 'LOW',
      summary: 'EBS Bandwidth Flag (Derived)',
      description: `EBS optimization changed to '${drift.actual_value}'. On AWS nitro-based instances (t3 family), EBS optimization is enabled by default. This is a direct side-effect of the EC2 instance type selection.`,
      costImpact: 'No additional charge on current generation instances.',
      complianceImpact: 'Informational dependency change.',
    };
  }

  if (prop === 'public_ip' || prop === 'public_dns') {
    return {
      riskLevel: 'LOW',
      summary: 'Ephemeral Ingress Endpoint Rotation',
      description: `Public address rotated from '${drift.desired_value}' to '${drift.actual_value}' following an EC2 stop/start lifecycle event. Non-elastic public IPs are dynamically released by AWS on shutdown.`,
      costImpact: 'None.',
      complianceImpact: 'External consumers accessing the instance via raw public IP instead of Route53 or Elastic IP will lose connectivity.',
    };
  }

  if (prop === 'instance_state') {
    return {
      riskLevel: 'MEDIUM',
      summary: 'Instance Lifecycle State',
      description: `Instance power state changed to '${drift.actual_value}'. If unexpectedly stopped, application availability and health checks will fail.`,
      costImpact: 'EBS and Elastic IP costs persist while compute billing stops.',
      complianceImpact: 'SLA availability breach if unexpected.',
    };
  }

  if (isConfig) {
    return {
      riskLevel: drift.severity || 'MEDIUM',
      summary: `Configuration Drift on ${drift.property}`,
      description: drift.reason || `The property '${drift.property}' on ${drift.resource_name} deviates from code.`,
      costImpact: 'Depends on resource specification.',
      complianceImpact: 'Violates Terraform state configuration as source-of-truth.',
    };
  }

  return {
    riskLevel: 'LOW',
    summary: `Runtime State Variation (${drift.property})`,
    description: drift.reason || `Transient runtime state attribute '${drift.property}' updated by AWS cloud provider.`,
    costImpact: 'Nominal / None.',
    complianceImpact: 'None (expected cloud runtime behavior).',
  };
}

/**
 * Generates structured corrective recommendations for a drift record.
 */
export function getDriftRecommendation(drift) {
  const prop = drift.property?.toLowerCase();
  const category = drift.category;
  const isConfig = category === 'CONFIGURATION_DRIFT';
  const isDependency = category === 'DEPENDENCY_CHANGE';

  // Specific EC2 instance type recommendations
  if (prop === 'instance_type') {
    return {
      whatChanged: `EC2 instance size changed from desired '${drift.desired_value}' (Terraform) to '${drift.actual_value}' (AWS).`,
      whyItMatters: 'Altering instance type outside IaC causes configuration divergence, unpredictable workload capacity (RAM/CPU halved), and risks Terraform destroying or rebooting the instance during subsequent applies.',
      recommendedPriority: 'HIGH',
      suggestedAction: `Remediation options:
1. Enforce Desired State (Recommended): Execute a targeted 'terraform apply -replace="${drift.resource_name}"' or stop the instance and resize via AWS CLI: 'aws ec2 modify-instance-attribute --instance-id <id> --instance-type "{\\"Value\\": \\"${drift.desired_value}\\"}"'.
2. Adopt Drifted State: If '${drift.actual_value}' was an intentional downscale, update your Terraform configuration file (e.g. main.tf) with 'instance_type = "${drift.actual_value}"' and commit the change to Git.`,
      actionCategory: 'Configuration Remediation',
      requiresApproval: true,
    };
  }

  // EBS optimized
  if (prop === 'ebs_optimized') {
    return {
      whatChanged: `EBS optimization changed from '${drift.desired_value}' to '${drift.actual_value}'.`,
      whyItMatters: 'This change is an automated AWS dependency consequence of changing the instance type family. It does not require separate manual intervention.',
      recommendedPriority: 'LOW',
      suggestedAction: `Resolve the parent '${drift.resource_name}' configuration drift (such as instance_type). Terraform will automatically synchronize the ebs_optimized flag once the primary attribute is reconciled.`,
      actionCategory: 'Dependency Resolution',
      requiresApproval: false,
    };
  }

  // Public IP / Public DNS
  if (prop === 'public_ip' || prop === 'public_dns') {
    return {
      whatChanged: `Public network address changed from '${drift.desired_value}' to '${drift.actual_value}'.`,
      whyItMatters: 'Standard EC2 public IPs are dynamic and re-allocated upon instance reboot. This is normal AWS behavior unless an Elastic IP is provisioned.',
      recommendedPriority: 'LOW',
      suggestedAction: `If this instance requires a static ingress address, allocate an 'aws_eip' resource in Terraform and associate it with '${drift.resource_name}'. If ephemeral addressing is expected, run 'terraform refresh' to update the state file without recreating resources.`,
      actionCategory: 'Runtime State Synchronization',
      requiresApproval: false,
    };
  }

  // Security group changes
  if (prop.includes('security_group')) {
    return {
      whatChanged: `Security group binding modified outside Terraform.`,
      whyItMatters: 'Manual security group modifications risk exposing management ports (SSH, RDP) or breaking internal microservice communication pathways.',
      recommendedPriority: 'CRITICAL',
      suggestedAction: `Audit CloudTrail for the 'ModifyInstanceAttribute' or 'AuthorizeSecurityGroupIngress' event to identify who made the change. Revert to '${drift.desired_value}' using 'terraform apply' after verifying security compliance.`,
      actionCategory: 'Security Remediation',
      requiresApproval: true,
    };
  }

  // Generic Configuration Drift
  if (isConfig) {
    return {
      whatChanged: `Property '${drift.property}' drifted from '${drift.desired_value}' to '${drift.actual_value}'.`,
      whyItMatters: drift.reason || 'Manual modifications in cloud provider consoles cause configuration drift and invalidate disaster recovery automation.',
      recommendedPriority: drift.severity === 'CRITICAL' ? 'CRITICAL' : drift.severity === 'HIGH' ? 'HIGH' : 'MEDIUM',
      suggestedAction: `Review change history in AWS CloudTrail. Decide whether to overwrite the live modification with 'terraform apply' or update your Terraform code to declare '${drift.actual_value}'.`,
      actionCategory: 'Configuration Remediation',
      requiresApproval: true,
    };
  }

  // Generic Dependency Change
  if (isDependency) {
    return {
      whatChanged: `Dependent attribute '${drift.property}' shifted to '${drift.actual_value}'.`,
      whyItMatters: drift.reason || 'Cascading property update triggered by a primary configuration change.',
      recommendedPriority: 'LOW',
      suggestedAction: `Address the root-cause configuration drift on the parent resource. Dependent state will automatically realign upon reconciliation.`,
      actionCategory: 'Dependency Resolution',
      requiresApproval: false,
    };
  }

  // Generic Runtime State Change
  return {
    whatChanged: `Runtime property '${drift.property}' updated to '${drift.actual_value}'.`,
    whyItMatters: drift.reason || 'Operational status updated during regular cloud provider lifecycle.',
    recommendedPriority: 'LOW',
    suggestedAction: `Run 'terraform refresh' during maintenance windows to capture normal runtime shifts into state without altering infrastructure.`,
    actionCategory: 'Runtime Synchronization',
    requiresApproval: false,
  };
}
