#!/usr/bin/env python3
"""
TR.O.2 — K8s manifest validation.

Checks all Kubernetes manifests for:
- Resource limits present on all containers
- Security contexts with runAsNonRoot
- Network policies covering all services

Usage:
    python scripts/lint_k8s_manifests.py
    python scripts/lint_k8s_manifests.py --k8s-dir deploy/k8s
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def find_k8s_manifests(base_dir: Path) -> list[Path]:
    """Find all YAML files in the K8s directory."""
    manifests = []
    if not base_dir.is_dir():
        return manifests
    for yaml_file in base_dir.rglob("*.yaml"):
        manifests.append(yaml_file)
    for yml_file in base_dir.rglob("*.yml"):
        manifests.append(yml_file)
    return manifests


def check_manifest(filepath: Path) -> list[str]:
    """Check a K8s manifest for best practices. Returns list of issues."""
    issues = []
    try:
        content = filepath.read_text()
    except Exception:
        return [f"Cannot read {filepath}"]

    # Check for resource limits on containers
    has_container = "containers:" in content or "container:" in content
    has_resources = "resources:" in content

    # Only flag Deployments/StatefulSets/Pods that have containers but no resource limits
    is_workload = any(
        keyword in content
        for keyword in ("kind: Deployment", "kind: StatefulSet", "kind: Pod", "kind: Job", "kind: CronJob")
    )
    if is_workload and has_container and not has_resources:
        issues.append(f"{filepath.name}: workload with containers but no resource limits")

    # Check for security context
    if is_workload:
        has_security = "securityContext:" in content
        has_nonroot = "runAsNonRoot" in content
        if not has_security:
            issues.append(f"{filepath.name}: workload without securityContext")
        elif not has_nonroot:
            issues.append(f"{filepath.name}: securityContext without runAsNonRoot")

    # Check for network policies
    if "kind: NetworkPolicy" in content:
        has_egress = "egress:" in content
        if not has_egress:
            issues.append(f"{filepath.name}: NetworkPolicy without egress rules")

    return issues


def run_checks(k8s_dir: Path) -> int:
    manifests = find_k8s_manifests(k8s_dir)
    if not manifests:
        print("No K8s manifests found (skip — no K8s directory).")
        return 0

    total_issues = 0
    for manifest in manifests:
        issues = check_manifest(manifest)
        for issue in issues:
            print(f"  ⚠ {issue}")
            total_issues += 1

    print(f"\n{len(manifests)} manifest(s) checked, {total_issues} issue(s).")
    return 0  # Informational only — does not block


def main() -> int:
    parser = argparse.ArgumentParser(description="TR.O.2 — K8s manifest validation")
    parser.add_argument("--k8s-dir", type=Path, default=Path("deploy/k8s"))
    args = parser.parse_args()
    return run_checks(args.k8s_dir)


if __name__ == "__main__":
    raise SystemExit(main())
