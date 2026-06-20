#!/usr/bin/env python3
"""
Verify Monitoring Configurations

This script verifies that monitoring configurations use standardized endpoint patterns:
- Prometheus metrics endpoint labels
- Grafana dashboard queries
- Jaeger operation names (if configured)
- Log aggregation patterns

Usage:
    python3 scripts/verify-monitoring-configurations.py
"""

import json
import sys
from pathlib import Path

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
]


def find_old_patterns_in_content(content: str, file_path: Path) -> list[tuple[int, str, str]]:
    """Find old patterns in content"""
    issues = []
    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        for old_pattern in OLD_PATTERNS:
            # Skip if it's a comment or documentation explaining old patterns
            if old_pattern in line:
                # Check if it's in a comment or documentation
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith("//"):
                    # Might be documentation - check context
                    if (
                        "deprecated" in line.lower()
                        or "old" in line.lower()
                        or "migration" in line.lower()
                    ):
                        continue  # OK - documenting old patterns

                # Check if standardized pattern is also present (might be comparison)
                has_standardized = any(pattern in line for pattern in STANDARDIZED_PATTERNS)
                if has_standardized:
                    continue  # OK - comparing old vs new

                issues.append((line_num, old_pattern, line.strip()[:100]))

    return issues


def check_prometheus_config(prometheus_file: Path) -> dict:
    """Check Prometheus configuration"""

    if not prometheus_file.exists():
        return {"file": str(prometheus_file), "exists": False, "issues": []}

    content = prometheus_file.read_text(encoding="utf-8")

    # Check for old patterns in scrape configs
    pattern_issues = find_old_patterns_in_content(content, prometheus_file)

    return {
        "file": str(prometheus_file),
        "exists": True,
        "issues": pattern_issues,
        "issue_count": len(pattern_issues),
    }


def check_grafana_dashboard(dashboard_file: Path) -> dict:
    """Check Grafana dashboard JSON"""
    issues = []

    if not dashboard_file.exists():
        return {"file": str(dashboard_file), "exists": False, "issues": []}

    try:
        content = dashboard_file.read_text(encoding="utf-8")
        dashboard = json.loads(content)

        # Check PromQL queries in targets
        def check_panels(panels):
            panel_issues = []
            for panel in panels:
                if "targets" in panel:
                    for target in panel["targets"]:
                        if "expr" in target:
                            expr = target["expr"]
                            for old_pattern in OLD_PATTERNS:
                                # Check if old pattern is in query (not in metric names like dq_runs_total)
                                if old_pattern in expr and "/api/v1/" in expr:
                                    panel_issues.append(
                                        {
                                            "panel": panel.get("title", "Unknown"),
                                            "pattern": old_pattern,
                                            "expr": expr[:200],
                                        }
                                    )
            return panel_issues

        # Check main panels
        if "dashboard" in dashboard and "panels" in dashboard["dashboard"]:
            issues.extend(check_panels(dashboard["dashboard"]["panels"]))

        # Check for old patterns in raw content (for non-JSON parts)
        content_issues = find_old_patterns_in_content(content, dashboard_file)
        issues.extend([(0, issue[1], issue[2]) for issue in content_issues])

    except json.JSONDecodeError as e:
        return {
            "file": str(dashboard_file),
            "exists": True,
            "error": f"Invalid JSON: {e}",
            "issues": [],
            "issue_count": 0,
        }

    return {
        "file": str(dashboard_file),
        "exists": True,
        "issues": issues,
        "issue_count": len(issues),
    }


def check_metrics_code(metrics_file: Path) -> dict:
    """Check metrics code for endpoint label patterns"""

    if not metrics_file.exists():
        return {"file": str(metrics_file), "exists": False, "issues": []}

    content = metrics_file.read_text(encoding="utf-8")

    # Check for hardcoded old endpoint patterns
    pattern_issues = find_old_patterns_in_content(content, metrics_file)

    # Filter out false positives (metric names like dq_runs_total are OK)
    filtered_issues = []
    for line_num, pattern, line in pattern_issues:
        # Skip if it's a metric name definition (not an endpoint path)
        if pattern in ["dq-runs", "compliance-runs"]:
            # Check if it's in a metric name context
            if "_runs_total" in line or "_runs_count" in line or "metric" in line.lower():
                continue  # OK - metric name
        filtered_issues.append((line_num, pattern, line))

    return {
        "file": str(metrics_file),
        "exists": True,
        "issues": filtered_issues,
        "issue_count": len(filtered_issues),
    }


def check_log_patterns(log_config_dir: Path) -> dict:
    """Check log aggregation patterns"""
    issues = []

    if not log_config_dir.exists():
        return {"dir": str(log_config_dir), "exists": False, "issues": []}

    # Look for log config files
    log_config_files = list(log_config_dir.glob("*.{yml,yaml,json,conf}"))

    for log_file in log_config_files:
        try:
            content = log_file.read_text(encoding="utf-8")
            pattern_issues = find_old_patterns_in_content(content, log_file)
            if pattern_issues:
                issues.extend([(str(log_file), issue) for issue in pattern_issues])
        except Exception:
            pass  # Skip files that can't be read

    return {
        "dir": str(log_config_dir),
        "exists": True,
        "issues": issues,
        "issue_count": len(issues),
    }


def main():
    """Main execution"""
    project_root = Path(__file__).resolve().parent.parent

    print("🔍 Verifying monitoring configurations...")
    print()

    all_issues = []

    # Check Prometheus configuration
    print("=" * 60)
    print("1. Prometheus Configuration")
    print("=" * 60)
    prometheus_file = project_root / "monitoring" / "prometheus" / "prometheus.yml"
    prometheus_result = check_prometheus_config(prometheus_file)

    if prometheus_result["exists"]:
        if prometheus_result["issue_count"] > 0:
            print(f"⚠️  {prometheus_file.name}: {prometheus_result['issue_count']} issues found")
            all_issues.extend(prometheus_result["issues"])
        else:
            print(f"✅ {prometheus_file.name}: No issues found")
    else:
        print(f"⚠️  {prometheus_file.name}: File not found")

    print()

    # Check Grafana dashboards
    print("=" * 60)
    print("2. Grafana Dashboards")
    print("=" * 60)
    dashboards_dir = project_root / "monitoring" / "grafana" / "dashboards"

    if dashboards_dir.exists():
        dashboard_files = list(dashboards_dir.glob("*.json"))
        dashboard_issues_count = 0

        for dashboard_file in sorted(dashboard_files):
            dashboard_result = check_grafana_dashboard(dashboard_file)

            if dashboard_result["issue_count"] > 0:
                print(f"⚠️  {dashboard_file.name}: {dashboard_result['issue_count']} issues found")
                dashboard_issues_count += dashboard_result["issue_count"]
                all_issues.extend(
                    [(dashboard_file.name, issue) for issue in dashboard_result["issues"]]
                )
            else:
                print(f"✅ {dashboard_file.name}: No issues found")

        if dashboard_issues_count == 0:
            print(f"\n✅ All {len(dashboard_files)} dashboards verified")
    else:
        print(f"⚠️  Dashboards directory not found: {dashboards_dir}")

    print()

    # Check metrics code
    print("=" * 60)
    print("3. Metrics Code")
    print("=" * 60)
    metrics_file = project_root / "hub" / "apps" / "observability" / "otel_metrics.py"
    metrics_result = check_metrics_code(metrics_file)

    if metrics_result["exists"]:
        if metrics_result["issue_count"] > 0:
            print(f"⚠️  {metrics_file.name}: {metrics_result['issue_count']} issues found")
            all_issues.extend(metrics_result["issues"])
        else:
            print(f"✅ {metrics_file.name}: No issues found")
    else:
        print(f"⚠️  {metrics_file.name}: File not found")

    print()

    # Check log patterns (if directory exists)
    print("=" * 60)
    print("4. Log Aggregation Patterns")
    print("=" * 60)
    log_config_dirs = [
        project_root / "monitoring" / "logs",
        project_root / "infrastructure" / "logs",
    ]

    log_issues_count = 0
    for log_dir in log_config_dirs:
        log_result = check_log_patterns(log_dir)
        if log_result["exists"] and log_result["issue_count"] > 0:
            print(f"⚠️  {log_dir.name}: {log_result['issue_count']} issues found")
            log_issues_count += log_result["issue_count"]
            all_issues.extend(log_result["issues"])
        elif log_result["exists"]:
            print(f"✅ {log_dir.name}: No issues found")

    if log_issues_count == 0:
        print("✅ No log pattern issues found")

    print()

    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    total_issues = len(all_issues)

    if total_issues == 0:
        print("✅ All monitoring configurations use standardized endpoint patterns!")
        return 0
    else:
        print(f"⚠️  Found {total_issues} issues:")
        for issue in all_issues[:10]:  # Show first 10
            if isinstance(issue, tuple):
                if len(issue) == 3:
                    print(f"  - Line {issue[0]}: {issue[1]} - {issue[2]}")
                else:
                    print(f"  - {issue}")
            else:
                print(f"  - {issue}")
        if total_issues > 10:
            print(f"  ... and {total_issues - 10} more")
        return 1


if __name__ == "__main__":
    sys.exit(main())
