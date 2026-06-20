#!/usr/bin/env python3
"""
Performance Comparison Script

This script compares performance baselines (e.g., Django 4.2 vs Django 6)
and identifies improvements and regressions.

Usage:
    python scripts/compare_performance.py --baseline baseline_django42.json --current baseline_django6.json --output comparison.json

Example:
    python scripts/compare_performance.py --baseline baseline_django42.json --current baseline_django6.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class PerformanceComparator:
    """Compares performance baselines"""

    def __init__(self, baseline: dict[str, Any], current: dict[str, Any]):
        self.baseline = baseline
        self.current = current
        self.comparison = {
            "baseline_version": baseline.get("django_version", "unknown"),
            "current_version": current.get("django_version", "unknown"),
            "baseline_timestamp": baseline.get("timestamp", "unknown"),
            "current_timestamp": current.get("timestamp", "unknown"),
            "improvements": [],
            "regressions": [],
            "unchanged": [],
            "metrics_comparison": {},
        }

    def compare_metrics(
        self,
        baseline_metrics: dict[str, float],
        current_metrics: dict[str, float],
        category: str,
        threshold: float = 0.1,
    ) -> dict[str, Any]:
        """Compare metrics and identify changes"""
        comparison = {}
        improvements = []
        regressions = []
        unchanged = []

        # Get all metric keys
        all_keys = set(baseline_metrics.keys()) | set(current_metrics.keys())

        for key in all_keys:
            baseline_value = baseline_metrics.get(key, 0)
            current_value = current_metrics.get(key, 0)

            if baseline_value == 0:
                continue  # Skip if baseline is 0

            change_percent = ((current_value - baseline_value) / baseline_value) * 100

            comparison[key] = {
                "baseline": baseline_value,
                "current": current_value,
                "change_percent": change_percent,
                "change_absolute": current_value - baseline_value,
            }

            # Categorize change
            if abs(change_percent) < threshold:
                unchanged.append(key)
            elif change_percent < -threshold:  # Negative change = improvement (lower is better)
                improvements.append(
                    {
                        "metric": key,
                        "improvement_percent": abs(change_percent),
                        "baseline": baseline_value,
                        "current": current_value,
                    }
                )
            elif change_percent > threshold:  # Positive change = regression (higher is worse)
                regressions.append(
                    {
                        "metric": key,
                        "regression_percent": change_percent,
                        "baseline": baseline_value,
                        "current": current_value,
                    }
                )

        return {
            "comparison": comparison,
            "improvements": improvements,
            "regressions": regressions,
            "unchanged": unchanged,
        }

    def compare_all(self):
        """Compare all performance metrics"""
        baseline_metrics = self.baseline.get("metrics", {})
        current_metrics = self.current.get("metrics", {})

        categories = [
            "api_response_times",
            "database_query_times",
            "jsonfield_query_times",
            "middleware_execution_times",
            "job_queue_processing_times",
            "file_storage_operations_times",
        ]

        for category in categories:
            baseline_cat = baseline_metrics.get(category, {})
            current_cat = current_metrics.get(category, {})

            if not baseline_cat or not current_cat:
                continue

            result = self.compare_metrics(baseline_cat, current_cat, category)
            self.comparison["metrics_comparison"][category] = result

            # Aggregate improvements and regressions
            self.comparison["improvements"].extend(
                [{**imp, "category": category} for imp in result["improvements"]]
            )
            self.comparison["regressions"].extend(
                [{**reg, "category": category} for reg in result["regressions"]]
            )

    def generate_report(self) -> str:
        """Generate human-readable report"""
        report = []
        report.append("=" * 80)
        report.append("Performance Comparison Report")
        report.append("=" * 80)
        report.append(
            f"Baseline: {self.comparison['baseline_version']} ({self.comparison['baseline_timestamp']})"
        )
        report.append(
            f"Current:  {self.comparison['current_version']} ({self.comparison['current_timestamp']})"
        )
        report.append("")

        # Improvements
        if self.comparison["improvements"]:
            report.append("✅ PERFORMANCE IMPROVEMENTS")
            report.append("-" * 80)
            for imp in sorted(
                self.comparison["improvements"],
                key=lambda x: x.get("improvement_percent", 0),
                reverse=True,
            )[:10]:
                report.append(f"  {imp['category']}.{imp['metric']}:")
                report.append(f"    Improvement: {imp.get('improvement_percent', 0):.2f}%")
                report.append(
                    f"    Baseline: {imp['baseline']:.3f}ms → Current: {imp['current']:.3f}ms"
                )
            report.append("")
        else:
            report.append("ℹ️  No significant performance improvements detected")
            report.append("")

        # Regressions
        if self.comparison["regressions"]:
            report.append("⚠️  PERFORMANCE REGRESSIONS")
            report.append("-" * 80)
            for reg in sorted(
                self.comparison["regressions"],
                key=lambda x: x.get("regression_percent", 0),
                reverse=True,
            )[:10]:
                report.append(f"  {reg['category']}.{reg['metric']}:")
                report.append(f"    Regression: {reg.get('regression_percent', 0):.2f}%")
                report.append(
                    f"    Baseline: {reg['baseline']:.3f}ms → Current: {reg['current']:.3f}ms"
                )
            report.append("")
        else:
            report.append("✅ No significant performance regressions detected")
            report.append("")

        # Summary
        report.append("=" * 80)
        report.append("Summary")
        report.append("=" * 80)
        report.append(f"Improvements: {len(self.comparison['improvements'])}")
        report.append(f"Regressions: {len(self.comparison['regressions'])}")
        report.append("")

        return "\n".join(report)

    def save_results(self, output_file: str):
        """Save comparison results to file"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(self.comparison, f, indent=2)

        print(f"✅ Comparison results saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Compare performance baselines")
    parser.add_argument(
        "--baseline", required=True, help="Baseline performance file (e.g., Django 4.2)"
    )
    parser.add_argument(
        "--current", required=True, help="Current performance file (e.g., Django 6)"
    )
    parser.add_argument(
        "--output",
        default="performance_comparison.json",
        help="Output file path (default: performance_comparison.json)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.1,
        help="Change threshold percentage (default: 0.1 = 10%%)",
    )

    args = parser.parse_args()

    # Load baseline files
    baseline_path = Path(args.baseline)
    current_path = Path(args.current)

    if not baseline_path.exists():
        print(f"❌ Error: Baseline file not found: {baseline_path}")
        return 1

    if not current_path.exists():
        print(f"❌ Error: Current file not found: {current_path}")
        return 1

    with open(baseline_path) as f:
        baseline = json.load(f)

    with open(current_path) as f:
        current = json.load(f)

    # Compare
    comparator = PerformanceComparator(baseline, current)
    comparator.compare_all()

    # Generate report
    report = comparator.generate_report()
    print(report)

    # Save results
    comparator.save_results(args.output)

    # Exit code based on regressions
    if comparator.comparison["regressions"]:
        print("\n⚠️  Performance regressions detected - review required")
        return 1
    else:
        print("\n✅ No performance regressions detected")
        return 0


if __name__ == "__main__":
    sys.exit(main())
