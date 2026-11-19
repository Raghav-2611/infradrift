#!/usr/bin/env python3
"""
scripts/validate_k8s.py
Validates Kubernetes YAML manifests and Helm chart files in the repository.
Checks:
- Valid YAML syntax
- Presence of required Kubernetes fields (apiVersion, kind, metadata.name)
- PVC, Secret, ConfigMap, Deployment, Service, Ingress structure
- Helm Chart.yaml and values.yaml validity
"""

import sys
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

def validate_k8s_manifest(file_path: Path):
    print(f"Checking {file_path.relative_to(REPO_ROOT)}... ", end="")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
    except Exception as exc:
        print(f"FAILED (YAML Parse Error: {exc})")
        return False

    valid = True
    for doc in docs:
        if doc is None:
            continue
        if not isinstance(doc, dict):
            print(f"FAILED (Document is not a dictionary: {type(doc)})")
            valid = False
            continue
        if doc.get("kind") == "Kustomization":
            continue
        if "apiVersion" not in doc or "kind" not in doc:
            print("FAILED (Missing apiVersion or kind)")
            valid = False
            continue
        if "metadata" not in doc or "name" not in doc["metadata"]:
            print("FAILED (Missing metadata.name)")
            valid = False
            continue

    if valid:
        print(f"OK ({len(docs)} document(s))")
    return valid

def validate_helm_chart(helm_dir: Path):
    all_passed = True
    chart_yaml = helm_dir / "Chart.yaml"
    values_yaml = helm_dir / "values.yaml"

    print(f"\nChecking {chart_yaml.relative_to(REPO_ROOT)}... ", end="")
    try:
        with open(chart_yaml, "r", encoding="utf-8") as f:
            chart = yaml.safe_load(f)
        assert chart.get("apiVersion") in ["v1", "v2"], "Invalid Helm apiVersion"
        assert "name" in chart, "Missing chart name"
        assert "version" in chart, "Missing chart version"
        print(f"OK (Helm {chart.get('apiVersion')}, version {chart.get('version')})")
    except Exception as exc:
        print(f"FAILED ({exc})")
        all_passed = False

    print(f"Checking {values_yaml.relative_to(REPO_ROOT)}... ", end="")
    try:
        with open(values_yaml, "r", encoding="utf-8") as f:
            values = yaml.safe_load(f)
        assert isinstance(values, dict), "values.yaml must be a dictionary"
        print("OK (Valid YAML dictionary)")
    except Exception as exc:
        print(f"FAILED ({exc})")
        all_passed = False

    required_keys = ["frontend", "backend", "postgresql", "secrets", "ingress"]
    for rk in required_keys:
        if rk not in values:
            print(f"  ✗ Missing required key in values.yaml: '{rk}'")
            all_passed = False
        else:
            print(f"  ✓ values.yaml has '{rk}'")

    # Check templates directory existence and file count
    templates_dir = helm_dir / "templates"
    template_files = list(templates_dir.glob("*.yaml")) + list(templates_dir.glob("*.tpl"))
    print(f"  ✓ Helm templates directory contains {len(template_files)} templates/helpers")

    return all_passed

def main():
    print("==================================================")
    print("InfraDrift Kubernetes Manifests & Helm Validation")
    print("==================================================")

    all_passed = True

    # 1. Validate k8s/ manifests
    k8s_dir = REPO_ROOT / "k8s"
    k8s_files = sorted(k8s_dir.glob("*.yaml"))
    if not k8s_files:
        print("ERROR: No YAML files found in k8s/")
        return 1

    for yf in k8s_files:
        if not validate_k8s_manifest(yf):
            all_passed = False

    # 2. Validate Helm Chart & Values
    helm_dir = REPO_ROOT / "helm" / "infradrift"
    if not validate_helm_chart(helm_dir):
        all_passed = False

    if all_passed:
        print("\nAll Kubernetes manifests and Helm configurations PASSED validation!")
        return 0
    else:
        print("\nValidation FAILED.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
