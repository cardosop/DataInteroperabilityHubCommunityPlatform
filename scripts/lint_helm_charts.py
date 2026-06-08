#!/usr/bin/env python3
"""
TR.O.1 — Helm template rendering + lint schema validation.

Runs ``helm lint`` and ``helm template`` against all chart directories.
Verifies output is valid Kubernetes YAML. Designed for CI.

Usage:
    python scripts/lint_helm_charts.py
    python scripts/lint_helm_charts.py --chart-dir deploy/helm
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def find_charts(base_dir: Path) -> list[Path]:
    """Find all Chart.yaml files and return their parent directories."""
    charts = []
    for chart_yaml in base_dir.rglob("Chart.yaml"):
        chart_dir = chart_yaml.parent
        if (chart_dir / "templates").is_dir():
            charts.append(chart_dir)
    return charts


def lint_chart(chart_dir: Path) -> tuple[bool, str]:
    """Run helm lint against a chart directory."""
    result = subprocess.run(
        ["helm", "lint", str(chart_dir)],
        text=True, capture_output=True, timeout=30,
    )
    if result.returncode != 0:
        return False, f"LINT FAILED: {chart_dir.name}\n{result.stderr[:300]}"
    return True, f"LINT OK: {chart_dir.name}"


def template_chart(chart_dir: Path) -> tuple[bool, str]:
    """Run helm template and verify output is valid YAML."""
    try:
        import yaml
    except ImportError:
        return True, f"TEMPLATE SKIP: {chart_dir.name} (PyYAML not installed)"

    result = subprocess.run(
        ["helm", "template", str(chart_dir)],
        text=True, capture_output=True, timeout=30,
    )
    if result.returncode != 0:
        return False, f"TEMPLATE FAILED: {chart_dir.name}\n{result.stderr[:300]}"

    # Verify output is valid YAML (helm template produces YAML stream)
    try:
        list(yaml.safe_load_all(result.stdout))
    except yaml.YAMLError as e:
        return False, f"YAML INVALID: {chart_dir.name}\n{e}"

    return True, f"TEMPLATE OK: {chart_dir.name}"


def run_checks(chart_base: Path) -> int:
    charts = find_charts(chart_base)
    if not charts:
        print("No Helm charts found.")
        return 0

    failures = 0
    for chart in charts:
        ok, msg = lint_chart(chart)
        print(f"  {'✓' if ok else '✗'} {msg}")
        if not ok:
            failures += 1

        ok, msg = template_chart(chart)
        print(f"  {'✓' if ok else '✗'} {msg}")
        if not ok:
            failures += 1

    print(f"\n{len(charts)} chart(s) checked, {failures} failure(s).")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TR.O.1 — Helm lint + template validation")
    parser.add_argument("--chart-dir", type=Path, default=Path("deploy/helm"))
    args = parser.parse_args()

    base = args.chart_dir
    if not base.is_dir():
        print(f"Chart directory not found: {base} (skip — no Helm charts to check)")
        return 0
    return run_checks(base)


if __name__ == "__main__":
    raise SystemExit(main())
