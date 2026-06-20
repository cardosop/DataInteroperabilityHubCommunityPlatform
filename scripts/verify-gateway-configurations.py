#!/usr/bin/env python3
"""
Verify API Gateway Configurations

This script verifies that API gateway configurations use standardized endpoint patterns:
- Traefik route configurations
- Kubernetes ingress rules

Usage:
    python3 scripts/verify-gateway-configurations.py
"""

import re
import sys
from pathlib import Path

import yaml

# Old patterns to check for
OLD_PATTERNS = [
    "/api/v1/compliance/compliance-runs/",
    "/api/v1/compliance/compliance-runs",
    "/api/v1/dq/dq-runs/",
    "/api/v1/dq/dq-runs",
    "compliance-runs",
    "dq-runs",
    "/compliance/scans/",
    "/compliance/scans",
]

# Standardized patterns
STANDARDIZED_PATTERNS = [
    "/api/v1/compliance/runs/",
    "/api/v1/compliance/runs",
    "/api/v1/dq/runs/",
    "/api/v1/dq/runs",
    "/api/v1/compliance",
    "/api/v1/dq",
]


def check_traefik_routes(routes_file: Path) -> dict:
    """Check Traefik routes configuration"""
    issues = []

    if not routes_file.exists():
        return {"file": str(routes_file), "exists": False, "issues": []}

    try:
        content = routes_file.read_text(encoding="utf-8")

        # Check for old patterns in route rules
        for old_pattern in OLD_PATTERNS:
            if old_pattern in content:
                # Check if it's in a PathPrefix rule
                if "PathPrefix" in content:
                    # Extract PathPrefix rules
                    pathprefix_pattern = r"PathPrefix\(`([^`]+)`\)"
                    matches = re.findall(pathprefix_pattern, content)

                    for match in matches:
                        if old_pattern in match:
                            issues.append(
                                {
                                    "type": "old_pattern_in_route",
                                    "pattern": old_pattern,
                                    "route": match,
                                    "line": content[: content.find(match)].count("\n") + 1,
                                }
                            )

        # Verify compliance and DQ routes use standardized patterns
        if "/api/v1/compliance" in content:
            # Should use /api/v1/compliance (not /api/v1/compliance/compliance-runs)
            if "/api/v1/compliance/compliance-runs" in content:
                issues.append(
                    {
                        "type": "old_compliance_pattern",
                        "pattern": "/api/v1/compliance/compliance-runs",
                        "message": "Should use /api/v1/compliance (runs handled by service)",
                    }
                )

        if "/api/v1/dq" in content:
            # Should use /api/v1/dq (not /api/v1/dq/dq-runs)
            if "/api/v1/dq/dq-runs" in content:
                issues.append(
                    {
                        "type": "old_dq_pattern",
                        "pattern": "/api/v1/dq/dq-runs",
                        "message": "Should use /api/v1/dq (runs handled by service)",
                    }
                )

        # Verify routes are properly configured
        if "compliance-service" in content:
            # Compliance service route should use /api/v1/compliance
            if "PathPrefix(`/api/v1/compliance`)" not in content:
                # Check if it exists at all
                if "compliance-service" in content and "PathPrefix" in content:
                    # Extract the rule for compliance-service
                    compliance_match = re.search(
                        r'compliance-service:.*?rule:\s*"PathPrefix\(`([^`]+)`\)"',
                        content,
                        re.DOTALL,
                    )
                    if compliance_match:
                        route_path = compliance_match.group(1)
                        if route_path != "/api/v1/compliance":
                            issues.append(
                                {
                                    "type": "incorrect_compliance_route",
                                    "found": route_path,
                                    "expected": "/api/v1/compliance",
                                }
                            )

        if "dq-service" in content:
            # DQ service route should use /api/v1/dq
            if "PathPrefix(`/api/v1/dq`)" not in content:
                # Check if it exists at all
                if "dq-service" in content and "PathPrefix" in content:
                    # Extract the rule for dq-service
                    dq_match = re.search(
                        r'dq-service:.*?rule:\s*"PathPrefix\(`([^`]+)`\)"', content, re.DOTALL
                    )
                    if dq_match:
                        route_path = dq_match.group(1)
                        if route_path != "/api/v1/dq":
                            issues.append(
                                {
                                    "type": "incorrect_dq_route",
                                    "found": route_path,
                                    "expected": "/api/v1/dq",
                                }
                            )

    except Exception as e:
        return {
            "file": str(routes_file),
            "exists": True,
            "error": str(e),
            "issues": [],
            "issue_count": 0,
        }

    return {"file": str(routes_file), "exists": True, "issues": issues, "issue_count": len(issues)}


def check_kubernetes_ingress(ingress_file: Path) -> dict:
    """Check Kubernetes ingress configuration"""
    issues = []

    if not ingress_file.exists():
        return {"file": str(ingress_file), "exists": False, "issues": []}

    try:
        content = ingress_file.read_text(encoding="utf-8")

        # Parse YAML
        ingress = yaml.safe_load(content)

        if not ingress or "spec" not in ingress:
            return {"file": str(ingress_file), "exists": True, "issues": [], "issue_count": 0}

        # Check rules
        if "rules" in ingress["spec"]:
            for rule in ingress["spec"]["rules"]:
                if "http" in rule and "paths" in rule["http"]:
                    for path in rule["http"]["paths"]:
                        path_value = path.get("path", "")

                        # Check for old patterns
                        for old_pattern in OLD_PATTERNS:
                            if old_pattern in path_value:
                                issues.append(
                                    {
                                        "type": "old_pattern_in_path",
                                        "pattern": old_pattern,
                                        "path": path_value,
                                    }
                                )

        # Check for compliance/dq service ingress
        metadata = ingress.get("metadata", {})
        name = metadata.get("name", "")

        if "compliance" in name.lower():
            # Compliance service ingress should use / or /api/v1/compliance
            # (not /compliance-runs)
            if "rules" in ingress["spec"]:
                for rule in ingress["spec"]["rules"]:
                    if "http" in rule and "paths" in rule["http"]:
                        for path in rule["http"]["paths"]:
                            path_value = path.get("path", "")
                            if "/compliance-runs" in path_value:
                                issues.append(
                                    {
                                        "type": "old_compliance_pattern_in_ingress",
                                        "path": path_value,
                                    }
                                )

        if "dq" in name.lower() or "dq-service" in name.lower():
            # DQ service ingress should use / or /api/v1/dq
            # (not /dq-runs)
            if "rules" in ingress["spec"]:
                for rule in ingress["spec"]["rules"]:
                    if "http" in rule and "paths" in rule["http"]:
                        for path in rule["http"]["paths"]:
                            path_value = path.get("path", "")
                            if "/dq-runs" in path_value:
                                issues.append(
                                    {"type": "old_dq_pattern_in_ingress", "path": path_value}
                                )

    except yaml.YAMLError as e:
        return {
            "file": str(ingress_file),
            "exists": True,
            "error": f"Invalid YAML: {e}",
            "issues": [],
            "issue_count": 0,
        }
    except Exception as e:
        return {
            "file": str(ingress_file),
            "exists": True,
            "error": str(e),
            "issues": [],
            "issue_count": 0,
        }

    return {"file": str(ingress_file), "exists": True, "issues": issues, "issue_count": len(issues)}


def main():
    """Main execution"""
    project_root = Path(__file__).resolve().parent.parent

    print("🔍 Verifying API gateway configurations...")
    print()

    all_issues = []

    # Check Traefik routes
    print("=" * 60)
    print("1. Traefik Route Configurations")
    print("=" * 60)

    traefik_routes = [
        project_root / "infrastructure" / "traefik" / "dynamic" / "routes.yml",
        project_root / "k8s" / "api-gateway" / "traefik" / "configmap.yaml",
    ]

    for routes_file in traefik_routes:
        result = check_traefik_routes(routes_file)

        if result["exists"]:
            if result["issue_count"] > 0:
                print(f"⚠️  {routes_file.name}: {result['issue_count']} issues found")
                all_issues.extend(result["issues"])
                for issue in result["issues"][:3]:
                    print(
                        f"   - {issue.get('type', 'unknown')}: {issue.get('pattern', issue.get('message', 'unknown'))}"
                    )
            else:
                print(f"✅ {routes_file.name}: No issues found")
        else:
            print(f"⚠️  {routes_file.name}: File not found")

    print()

    # Check Kubernetes ingress rules
    print("=" * 60)
    print("2. Kubernetes Ingress Rules")
    print("=" * 60)

    ingress_files = list((project_root / "k8s").rglob("**/ingress.yaml"))

    ingress_issues_count = 0
    for ingress_file in sorted(ingress_files):
        result = check_kubernetes_ingress(ingress_file)

        if result["exists"]:
            if result["issue_count"] > 0:
                print(
                    f"⚠️  {ingress_file.relative_to(project_root)}: {result['issue_count']} issues found"
                )
                ingress_issues_count += result["issue_count"]
                all_issues.extend(result["issues"])
                for issue in result["issues"][:3]:
                    print(
                        f"   - {issue.get('type', 'unknown')}: {issue.get('path', issue.get('pattern', 'unknown'))}"
                    )
            else:
                print(f"✅ {ingress_file.name}: No issues found")

    if ingress_issues_count == 0:
        print(f"\n✅ All {len(ingress_files)} ingress files verified")

    print()

    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    total_issues = len(all_issues)

    if total_issues == 0:
        print("✅ All API gateway configurations use standardized endpoint patterns!")
        return 0
    else:
        print(f"⚠️  Found {total_issues} issues:")
        for issue in all_issues[:10]:  # Show first 10
            print(
                f"  - {issue.get('type', 'unknown')}: {issue.get('pattern', issue.get('path', issue.get('message', 'unknown')))}"
            )
        if total_issues > 10:
            print(f"  ... and {total_issues - 10} more")
        return 1


if __name__ == "__main__":
    sys.exit(main())
