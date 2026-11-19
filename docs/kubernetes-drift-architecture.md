# InfraDrift — Kubernetes & Helm Drift Detection Architecture

## 1. Executive Summary

InfraDrift is expanding from AWS/Terraform cloud infrastructure drift detection to support **multi-source drift detection**, incorporating **Kubernetes & Helm workload drift**.

This architecture defines how InfraDrift will speculatively compare:
1. **Desired State**: Defined in Git repositories and rendered via Helm charts or Kustomize manifests.
2. **Actual State**: Running live inside the Kubernetes cluster, inspected via the Kubernetes Core & Apps API.

Detected changes are harmonized into the existing InfraDrift dashboard alongside Terraform drifts, tagged with `source: KUBERNETES_HELM` vs `source: AWS_TERRAFORM`.

---

## 2. Architectural Diagram

```
       ┌───────────────────────────────┐        ┌───────────────────────────────┐
       │     Desired State Sources     │        │      Actual State Source      │
       │  • Git Repository             │        │  • Kubernetes API Server      │
       │  • Rendered Helm Templates    │        │  • CoreV1Api, AppsV1Api       │
       │  • Kustomize Overlays         │        │  • RBAC Read-Only Collector   │
       └───────────────┬───────────────┘        └───────────────┬───────────────┘
                       │                                        │
                       │ Desired Manifest Tree                  │ Live Resource Tree
                       ▼                                        ▼
       ┌────────────────────────────────────────────────────────────────────────┐
       │                 InfraDrift Kubernetes Drift Engine                     │
       │                                                                        │
       │  1. Object Normalizer: Strips cluster-assigned metadata               │
       │     (uid, resourceVersion, generation, status, managedFields)          │
       │  2. Spec Diff Analyzer: Field-level three-way comparison              │
       │  3. Severity & Category Classifier                                    │
       └───────────────────────────────────┬────────────────────────────────────┘
                                           │
                                           ▼
                       ┌───────────────────────────────────────┐
                       │       Unified Drift Repository        │
                       │                                       │
                       │  DriftRecord(                         │
                       │    source="KUBERNETES_HELM",          │
                       │    resource_type="Deployment",        │
                       │    resource_name="frontend",          │
                       │    property="spec.replicas",          │
                       │    desired_value="2",                 │
                       │    actual_value="5",                  │
                       │    severity="HIGH",                   │
                       │    category="RUNTIME_STATE_CHANGE"    │
                       │  )                                    │
                       └───────────────────┬───────────────────┘
                                           │
                                           ▼
                       ┌───────────────────────────────────────┐
                       │       Existing InfraDrift UI          │
                       │                                       │
                       │  • Filter by Source (AWS vs K8s)      │
                       │  • Source Badge Pills [AWS] [K8S]     │
                       │  • Unified History & Analytics        │
                       └───────────────────────────────────────┘
```

---

## 3. Detected Drift Dimensions

The Kubernetes Drift Engine detects modifications across seven key operational dimensions:

| Dimension | Target Resources | Description | Default Severity |
|---|---|---|---|
| **Replica Drift** | `Deployment`, `StatefulSet` | Differences between `spec.replicas` in Git/Helm vs live cluster (e.g. manual `kubectl scale` without HPA). | `HIGH` |
| **Image & Tag Drift** | `Pod`, `Deployment`, `DaemonSet` | Discrepancies in `spec.template.spec.containers[*].image` (e.g. untracked hotfix images or tag overrides). | `CRITICAL` |
| **Environment Variable Drift** | All Workloads | Addition, removal, or divergence of environment variables in `env` or `envFrom`. | `HIGH` |
| **Resource Limits & Requests** | Containers | Divergence in CPU/Memory `requests` and `limits`, risking node contention or OOMKills. | `MEDIUM` |
| **Service & Port Drift** | `Service` | Changes to `spec.ports`, `spec.type` (e.g. ClusterIP changed to LoadBalancer), or `spec.selector`. | `HIGH` |
| **Configuration Drift** | `ConfigMap`, `Secret` | Differences in data keys or values between Git and cluster. | `HIGH` |
| **Orphaned / Missing Resources** | All K8s Kinds | Resources defined in Git but missing in cluster, or resources present in namespace not declared in Git. | `HIGH` / `MEDIUM` |

---

## 4. Kubernetes API Collector & Normalization Engine

### A. Read-Only RBAC Permissions
The collector uses an in-cluster or kubeconfig-authenticated `kubernetes` client with read-only ClusterRole permissions:
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: infradrift-k8s-collector-role
rules:
  - apiGroups: ["", "apps", "networking.k8s.io", "batch"]
    resources:
      - deployments
      - statefulsets
      - daemonsets
      - services
      - configmaps
      - ingresses
    verbs: ["get", "list", "watch"]
```

### B. Normalization Rules
Live Kubernetes resources contain server-generated metadata that must be ignored during diff calculation:
- `metadata.uid`, `metadata.resourceVersion`, `metadata.generation`, `metadata.creationTimestamp`
- `metadata.managedFields`
- `status` blocks
- Default admission controller injections (e.g., default service account volume mounts, default token projections)

---

## 5. Unified Dashboard Presentation

1. **Source Labeling**:
   - `AWS (Terraform)`: Displayed with an amber badge `[AWS]`.
   - `Kubernetes (Helm)`: Displayed with a blue badge `[K8S]`.

2. **Multi-Source Filtering**:
   - The dashboard `DriftTable` includes a dedicated **SOURCE** filter:
     - `All Sources` (combined view)
     - `AWS (Terraform)`
     - `K8s (Helm)`

3. **Safety Guarantee**:
   - As with Terraform reconciliation, automatic remediation for Kubernetes remains strictly disabled in Phase K.
   - Any remediation will follow the Safe Reconciliation multi-signature review workflow.
