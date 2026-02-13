#!/usr/bin/env python3
"""
Test Validation Module

Validates test results and coverage requirements:
- All tests passing
- Coverage requirements met
- Performance targets met
- Security requirements met
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class TestValidator:
    """Validates test execution results and requirements."""

    def __init__(self, report_dir: Path):
        self.report_dir = report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def validate_test_results(
        self, results: Dict[str, Any], output_file: Optional[Path] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Validate that all tests are passing."""
        if output_file is None:
            output_file = self.report_dir / "test_validation_report.txt"

        validation_results = {
            "timestamp": datetime.now().isoformat(),
            "all_tests_passing": True,
            "coverage_requirements_met": True,
            "performance_targets_met": True,
            "security_requirements_met": True,
            "issues": [],
            "warnings": [],
        }

        # Check if all tests are passing
        for test_type, result in results.items():
            if not result.get("success", False):
                validation_results["all_tests_passing"] = False
                validation_results["issues"].append(
                    {
                        "test_type": test_type,
                        "issue": f"Tests failed: {result.get('failed', 0)} failed, {result.get('errors', 0)} errors",
                        "status": result.get("status", "UNKNOWN"),
                    }
                )

        # Generate validation report
        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("TEST VALIDATION REPORT\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            f.write("VALIDATION RESULTS\n")
            f.write("-" * 80 + "\n")

            f.write(
                f"All Tests Passing: {'✅ YES' if validation_results['all_tests_passing'] else '❌ NO'}\n"
            )
            f.write(
                f"Coverage Requirements Met: {'✅ YES' if validation_results['coverage_requirements_met'] else '❌ NO'}\n"
            )
            f.write(
                f"Performance Targets Met: {'✅ YES' if validation_results['performance_targets_met'] else '❌ NO'}\n"
            )
            f.write(
                f"Security Requirements Met: {'✅ YES' if validation_results['security_requirements_met'] else '❌ NO'}\n\n"
            )

            if validation_results["issues"]:
                f.write("ISSUES FOUND\n")
                f.write("-" * 80 + "\n")
                for issue in validation_results["issues"]:
                    f.write(f"\n{issue['test_type'].upper()}:\n")
                    f.write(f"  Issue: {issue['issue']}\n")
                    f.write(f"  Status: {issue['status']}\n")

            if validation_results["warnings"]:
                f.write("\nWARNINGS\n")
                f.write("-" * 80 + "\n")
                for warning in validation_results["warnings"]:
                    f.write(f"  - {warning}\n")

            f.write("\n" + "=" * 80 + "\n")

        all_valid = (
            validation_results["all_tests_passing"]
            and validation_results["coverage_requirements_met"]
            and validation_results["performance_targets_met"]
            and validation_results["security_requirements_met"]
        )

        return all_valid, validation_results

    def validate_coverage_requirements(
        self,
        coverage_data: Dict[str, Any],
        min_coverage: float = 80.0,
        output_file: Optional[Path] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Validate that coverage requirements are met."""
        if output_file is None:
            output_file = self.report_dir / "coverage_validation_report.txt"

        validation_results = {
            "timestamp": datetime.now().isoformat(),
            "requirements_met": True,
            "overall_coverage": 0.0,
            "min_required": min_coverage,
            "issues": [],
        }

        # Calculate overall coverage
        if "totals" in coverage_data:
            totals = coverage_data["totals"]
            validation_results["overall_coverage"] = totals.get("percent_covered", 0.0)

            if validation_results["overall_coverage"] < min_coverage:
                validation_results["requirements_met"] = False
                validation_results["issues"].append(
                    {
                        "issue": f"Overall coverage {validation_results['overall_coverage']:.2f}% is below required {min_coverage}%",
                        "severity": "HIGH",
                    }
                )

        # Check per-file coverage
        if "files" in coverage_data:
            low_coverage_files = []
            for file_path, file_data in coverage_data["files"].items():
                summary = file_data.get("summary", {})
                coverage = summary.get("percent_covered", 0)

                if coverage < min_coverage:
                    low_coverage_files.append(
                        {
                            "file": file_path,
                            "coverage": coverage,
                        }
                    )

            if low_coverage_files:
                validation_results["issues"].append(
                    {
                        "issue": f"Found {len(low_coverage_files)} files below {min_coverage}% coverage",
                        "severity": "MEDIUM",
                        "files": low_coverage_files[:10],  # Top 10
                    }
                )

        # Generate validation report
        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("COVERAGE VALIDATION REPORT\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            f.write("COVERAGE VALIDATION RESULTS\n")
            f.write("-" * 80 + "\n")

            f.write(
                f"Requirements Met: {'✅ YES' if validation_results['requirements_met'] else '❌ NO'}\n"
            )
            f.write(f"Overall Coverage: {validation_results['overall_coverage']:.2f}%\n")
            f.write(f"Minimum Required: {validation_results['min_required']:.2f}%\n\n")

            if validation_results["issues"]:
                f.write("ISSUES FOUND\n")
                f.write("-" * 80 + "\n")
                for issue in validation_results["issues"]:
                    f.write(f"\n{issue['severity']} SEVERITY:\n")
                    f.write(f"  {issue['issue']}\n")
                    if "files" in issue:
                        f.write("  Affected Files:\n")
                        for file_info in issue["files"]:
                            f.write(f"    - {file_info['file']} ({file_info['coverage']:.2f}%)\n")

            f.write("\n" + "=" * 80 + "\n")

        return validation_results["requirements_met"], validation_results

    def validate_performance_targets(
        self,
        performance_data: Dict[str, Any],
        targets: Optional[Dict[str, Any]] = None,
        output_file: Optional[Path] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Validate that performance targets are met."""
        if output_file is None:
            output_file = self.report_dir / "performance_validation_report.txt"

        if targets is None:
            # Default performance targets
            targets = {
                "p95_latency_ms": 300,  # 300ms for P95 latency
                "p99_latency_ms": 500,  # 500ms for P99 latency
                "error_rate_percent": 0.5,  # 0.5% error rate
                "throughput_rps": 30,  # 30 requests per second
            }

        validation_results = {
            "timestamp": datetime.now().isoformat(),
            "targets_met": True,
            "targets": targets,
            "issues": [],
        }

        # Validate performance metrics
        if "metrics" in performance_data:
            metrics = performance_data["metrics"]

            # Check latency targets
            if "p95_latency_ms" in metrics:
                p95 = metrics["p95_latency_ms"]
                target = targets.get("p95_latency_ms", 300)
                if p95 > target:
                    validation_results["targets_met"] = False
                    validation_results["issues"].append(
                        {
                            "metric": "P95 Latency",
                            "value": p95,
                            "target": target,
                            "issue": f"P95 latency {p95}ms exceeds target {target}ms",
                        }
                    )

            if "p99_latency_ms" in metrics:
                p99 = metrics["p99_latency_ms"]
                target = targets.get("p99_latency_ms", 500)
                if p99 > target:
                    validation_results["targets_met"] = False
                    validation_results["issues"].append(
                        {
                            "metric": "P99 Latency",
                            "value": p99,
                            "target": target,
                            "issue": f"P99 latency {p99}ms exceeds target {target}ms",
                        }
                    )

            # Check error rate
            if "error_rate_percent" in metrics:
                error_rate = metrics["error_rate_percent"]
                target = targets.get("error_rate_percent", 0.5)
                if error_rate > target:
                    validation_results["targets_met"] = False
                    validation_results["issues"].append(
                        {
                            "metric": "Error Rate",
                            "value": error_rate,
                            "target": target,
                            "issue": f"Error rate {error_rate}% exceeds target {target}%",
                        }
                    )

            # Check throughput
            if "throughput_rps" in metrics:
                throughput = metrics["throughput_rps"]
                target = targets.get("throughput_rps", 30)
                if throughput < target:
                    validation_results["targets_met"] = False
                    validation_results["issues"].append(
                        {
                            "metric": "Throughput",
                            "value": throughput,
                            "target": target,
                            "issue": f"Throughput {throughput} RPS is below target {target} RPS",
                        }
                    )

        # Generate validation report
        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("PERFORMANCE VALIDATION REPORT\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            f.write("PERFORMANCE VALIDATION RESULTS\n")
            f.write("-" * 80 + "\n")

            f.write(
                f"Targets Met: {'✅ YES' if validation_results['targets_met'] else '❌ NO'}\n\n"
            )

            f.write("Performance Targets:\n")
            for metric, target in targets.items():
                f.write(f"  {metric}: {target}\n")

            if validation_results["issues"]:
                f.write("\nISSUES FOUND\n")
                f.write("-" * 80 + "\n")
                for issue in validation_results["issues"]:
                    f.write(f"\n{issue['metric']}:\n")
                    f.write(f"  Value: {issue['value']}\n")
                    f.write(f"  Target: {issue['target']}\n")
                    f.write(f"  Issue: {issue['issue']}\n")

            f.write("\n" + "=" * 80 + "\n")

        return validation_results["targets_met"], validation_results

    def validate_security_requirements(
        self, security_data: Dict[str, Any], output_file: Optional[Path] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Validate that security requirements are met."""
        if output_file is None:
            output_file = self.report_dir / "security_validation_report.txt"

        validation_results = {
            "timestamp": datetime.now().isoformat(),
            "requirements_met": True,
            "issues": [],
            "vulnerabilities": [],
        }

        # Check for vulnerabilities
        if "vulnerabilities" in security_data:
            vulnerabilities = security_data["vulnerabilities"]
            critical_vulns = [
                v for v in vulnerabilities if v.get("severity", "").upper() == "CRITICAL"
            ]
            high_vulns = [v for v in vulnerabilities if v.get("severity", "").upper() == "HIGH"]

            if critical_vulns:
                validation_results["requirements_met"] = False
                validation_results["issues"].append(
                    {
                        "severity": "CRITICAL",
                        "issue": f"Found {len(critical_vulns)} critical vulnerabilities",
                        "count": len(critical_vulns),
                    }
                )

            if high_vulns:
                validation_results["issues"].append(
                    {
                        "severity": "HIGH",
                        "issue": f"Found {len(high_vulns)} high severity vulnerabilities",
                        "count": len(high_vulns),
                    }
                )

            validation_results["vulnerabilities"] = vulnerabilities

        # Check test results
        if "results" in security_data:
            results = security_data["results"]
            failed_tests = [r for r in results.values() if r.get("status", "").upper() != "PASSED"]

            if failed_tests:
                validation_results["requirements_met"] = False
                validation_results["issues"].append(
                    {
                        "severity": "HIGH",
                        "issue": f"Found {len(failed_tests)} failed security tests",
                        "count": len(failed_tests),
                    }
                )

        # Generate validation report
        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("SECURITY VALIDATION REPORT\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            f.write("SECURITY VALIDATION RESULTS\n")
            f.write("-" * 80 + "\n")

            f.write(
                f"Requirements Met: {'✅ YES' if validation_results['requirements_met'] else '❌ NO'}\n\n"
            )

            if validation_results["issues"]:
                f.write("ISSUES FOUND\n")
                f.write("-" * 80 + "\n")
                for issue in validation_results["issues"]:
                    f.write(f"\n{issue['severity']} SEVERITY:\n")
                    f.write(f"  {issue['issue']}\n")
                    f.write(f"  Count: {issue['count']}\n")

            if validation_results["vulnerabilities"]:
                f.write("\nVULNERABILITIES\n")
                f.write("-" * 80 + "\n")
                for vuln in validation_results["vulnerabilities"]:
                    f.write(f"\n{vuln.get('name', 'Unknown')}:\n")
                    f.write(f"  Severity: {vuln.get('severity', 'UNKNOWN')}\n")
                    f.write(f"  Description: {vuln.get('description', 'N/A')}\n")

            f.write("\n" + "=" * 80 + "\n")

        return validation_results["requirements_met"], validation_results


if __name__ == "__main__":
    # Example usage
    report_dir = Path("test_reports")
    validator = TestValidator(report_dir)

    print("Test validation module initialized.")
    print(f"Report directory: {report_dir}")
