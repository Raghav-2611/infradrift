"""
services/aws_service.py

Lightweight AWS helper — queries EC2 directly to confirm the real
(live) instance type for a given instance ID.

Credentials are resolved by boto3 in this order:
  1. Environment variables (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)
  2. ~/.aws/credentials (aws configure)
  3. EC2 Instance Metadata Service (IAM role attached to the instance)

Never hardcode credentials here.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import boto3  # optional — only needed when cross-checking live AWS state
    _BOTO3_AVAILABLE = True
except ImportError:
    _BOTO3_AVAILABLE = False


def get_instance_type(instance_id: str, region: str = "us-east-1") -> str | None:
    """
    Return the current (live) instance type for the given EC2 instance ID,
    or None if boto3 is not installed or the instance cannot be found.

    Args:
        instance_id: EC2 instance ID, e.g. "i-0abc1234def56789a".
        region: AWS region the instance lives in.

    Returns:
        str | None: The live instance type (e.g. "t3.micro") or None.
    """
    if not _BOTO3_AVAILABLE:
        logger.warning(
            "boto3 is not installed; skipping live AWS cross-check for %s.", instance_id
        )
        return None

    try:
        ec2 = boto3.client("ec2", region_name=region)
        response = ec2.describe_instances(InstanceIds=[instance_id])
        reservations = response.get("Reservations", [])
        if not reservations:
            logger.warning("No EC2 reservation found for instance %s.", instance_id)
            return None
        instance = reservations[0]["Instances"][0]
        return instance.get("InstanceType")
    except Exception as exc:  # noqa: BLE001
        logger.error("AWS EC2 describe_instances failed for %s: %s", instance_id, exc)
        return None
