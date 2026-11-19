# InfraDrift — AWS EKS & Kubernetes Deployment Guide

This guide details the production deployment process for the **InfraDrift** drift detection platform to an Amazon Elastic Kubernetes Service (EKS) cluster using Helm.

---

## 1. Architecture Overview in Kubernetes

```
                      ┌────────────────────────────────────────┐
                      │          AWS Application Load          │
                      │          Balancer (ALB / Ingress)      │
                      └──────────────────┬─────────────────────┘
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   │                                           │
         Path: / (UI / Static)                     Path: /api, /health
                   │                                           │
                   ▼                                           ▼
       ┌───────────────────────┐                   ┌───────────────────────┐
       │  infradrift-frontend  │                   │  infradrift-backend   │
       │    Service (Port 80)  │                   │   Service (Port 8000) │
       └───────────┬───────────┘                   └───────────┬───────────┘
                   │                                           │
                   ▼                                           ▼
       ┌───────────────────────┐                   ┌───────────────────────┐
       │   Frontend Pods (x2)  │                   │   Backend Pods (x2)   │
       │   Nginx + React SPA   │                   │   FastAPI + Terraform │
       └───────────────────────┘                   └───────────┬───────────┘
                                                               │
                                         ClusterIP: 5432       │
                                         (Strictly Internal)   │
                                                               ▼
                                                   ┌───────────────────────┐
                                                   │  infradrift-postgres  │
                                                   │     PostgreSQL 16     │
                                                   └───────────┬───────────┘
                                                               │
                                                               ▼
                                                   ┌───────────────────────┐
                                                   │  EBS PVC (gp3, 10Gi)  │
                                                   └───────────────────────┘
```

---

## 2. EKS Cluster Prerequisites

Before deploying InfraDrift, ensure your AWS account has the following cluster infrastructure:

| Component | Minimum Specification | Notes |
|---|---|---|
| **EKS Kubernetes Version** | `1.28+` | Compatible through current 1.30+ |
| **VPC & Subnets** | Multi-AZ (at least 2 Public & 2 Private) | Public for Load Balancer / NAT, Private for Worker Nodes |
| **Node Group** | 2 × `t3.medium` or `m5.large` | Minimum 2 nodes for high availability and rolling updates |
| **EBS CSI Driver** | `aws-ebs-csi-driver` EKS add-on | Required for dynamic provisioning of PostgreSQL `PersistentVolumeClaim` |
| **Ingress Controller** | AWS Load Balancer Controller or `ingress-nginx` | Routes public traffic to frontend and backend services |

---

## 3. IAM Roles & Permissions (IRSA)

The InfraDrift backend executes speculatively (`terraform plan -refresh-only`) to inspect live AWS state. To adhere to least-privilege security without static credentials, use **IAM Roles for Service Accounts (IRSA)**.

### A. Create an IAM Policy for Backend State Inspection
Create `InfraDriftDriftReadPolicy` with read-only permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InfraDriftReadOnlyEC2",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceStatus",
        "ec2:DescribeInstanceTypes",
        "ec2:DescribeInstanceAttribute",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets",
        "ec2:DescribeVolumes"
      ],
      "Resource": "*"
    }
  ]
}
```

### B. Associate IAM Role with Kubernetes Service Account
```bash
eksctl create iamserviceaccount \
  --name infradrift-backend-sa \
  --namespace infradrift \
  --cluster <YOUR_EKS_CLUSTER_NAME> \
  --region <AWS_REGION> \
  --attach-policy-arn arn:aws:iam::<ACCOUNT_ID>:policy/InfraDriftDriftReadPolicy \
  --approve
```

---

## 4. Container Image Build and ECR Push

### A. Authenticate Docker with Amazon ECR
```bash
aws ecr get-login-password --region <AWS_REGION> | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com
```

### B. Create ECR Repositories (if not already created)
```bash
aws ecr create-repository --repository-name infradrift-frontend --region <AWS_REGION>
aws ecr create-repository --repository-name infradrift-backend --region <AWS_REGION>
```

### C. Build and Push Frontend Image
```bash
docker build -t <ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/infradrift-frontend:v0.2.0 -f Dockerfile .
docker push <ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/infradrift-frontend:v0.2.0
```

### D. Build and Push Backend Image
```bash
docker build -t <ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/infradrift-backend:v0.2.0 -f backend/Dockerfile .
docker push <ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/infradrift-backend:v0.2.0
```

---

## 5. Helm Deployment to EKS

### A. Deploy with Helm
```bash
# 1. Create a production values file or pass parameters directly:
helm install infradrift ./helm/infradrift \
  --namespace infradrift \
  --create-namespace \
  --set frontend.image.repository=<ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/infradrift-frontend \
  --set frontend.image.tag=v0.2.0 \
  --set backend.image.repository=<ACCOUNT_ID>.dkr.ecr.<AWS_REGION>.amazonaws.com/infradrift-backend \
  --set backend.image.tag=v0.2.0 \
  --set secrets.postgresPassword="$(openssl rand -base64 24)" \
  --set ingress.enabled=true \
  --set ingress.className=alb
```

### B. Upgrade Existing Release
```bash
helm upgrade infradrift ./helm/infradrift \
  --namespace infradrift \
  --set frontend.image.tag=v0.2.1 \
  --set backend.image.tag=v0.2.1
```

### C. Rollback in Case of Failure
```bash
# View release history
helm history infradrift --namespace infradrift

# Rollback to previous revision (e.g. revision 1)
helm rollback infradrift 1 --namespace infradrift
```

### D. Uninstall Release
```bash
helm uninstall infradrift --namespace infradrift
```

---

## 6. Deployment Verification & Troubleshooting

### Check Pod Status
```bash
kubectl get pods -n infradrift -l app.kubernetes.io/name=infradrift -o wide
```

### Verify PostgreSQL Volume Mount
```bash
kubectl get pvc,pv -n infradrift
```

### Test Backend Liveness and Readiness
```bash
# Liveness
kubectl exec -it -n infradrift deploy/infradrift-backend -- curl -s http://localhost:8000/health/live

# Readiness (confirms DB connectivity and health)
kubectl exec -it -n infradrift deploy/infradrift-backend -- curl -s http://localhost:8000/health/ready
```

### View Live Logs
```bash
# Backend application logs
kubectl logs -n infradrift -l app.kubernetes.io/component=backend -f --tail=100

# Frontend web server logs
kubectl logs -n infradrift -l app.kubernetes.io/component=frontend -f --tail=100
```
