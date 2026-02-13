#!/usr/bin/env python3
"""
Test Reporting Module

Generates comprehensive test execution reports including:
- Test execution summary
- Coverage reports (unit, integration, E2E)
- Performance test reports
- Security test reports
- Coverage analysis by module and feature
"""
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class TestReportGenerator:
    """Generates comprehensive test reports."""

    def __init__(self, report_dir: Path):
        self.report_dir = report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate_execution_report(
        self, results: Dict[str, Any], output_file: Optional[Path] = None
    ) -> Path:
        """Generate comprehensive test execution report."""
        if output_file is None:
            output_file = self.report_dir / "test_execution_report.txt"

        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("COMPREHENSIVE TEST EXECUTION REPORT\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            # Overall summary
            f.write("OVERALL SUMMARY\n")
            f.write("-" * 80 + "\n")

            total_tests = sum(r.get("total_tests", 0) for r in results.values())
            total_passed = sum(r.get("passed", 0) for r in results.values())
            total_failed = sum(r.get("failed", 0) for r in results.values())
            total_errors = sum(r.get("errors", 0) for r in results.values())
            total_skipped = sum(r.get("skipped", 0) for r in results.values())

            f.write(f"Total Tests: {total_tests}\n")
            f.write(f"Passed: {total_passed}\n")
            f.write(f"Failed: {total_failed}\n")
            f.write(f"Errors: {total_errors}\n")
            f.write(f"Skipped: {total_skipped}\n")

            success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
            f.write(f"Success Rate: {success_rate:.2f}%\n\n")

            # Per-category results
            f.write("CATEGORY RESULTS\n")
            f.write("-" * 80 + "\n")

            for test_type, result in results.items():
                f.write(f"\n{test_type.upper()} Tests:\n")
                f.write(f"  Status: {result.get('status', 'UNKNOWN')}\n")
                f.write(f"  Duration: {result.get('duration', 0):.2f} seconds\n")
                f.write(f"  Total Tests: {result.get('total_tests', 0)}\n")
                f.write(f"  Passed: {result.get('passed', 0)}\n")
                f.write(f"  Failed: {result.get('failed', 0)}\n")
                f.write(f"  Errors: {result.get('errors', 0)}\n")
                f.write(f"  Skipped: {result.get('skipped', 0)}\n")

                if result.get("error_message"):
                    f.write(f"  Error: {result['error_message']}\n")

            f.write("\n" + "=" * 80 + "\n")

        return output_file

    def generate_coverage_report(
        self, coverage_data: Dict[str, Any], output_file: Optional[Path] = None
    ) -> Path:
        """Generate test coverage report."""
        if output_file is None:
            output_file = self.report_dir / "test_coverage_report.txt"

        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("TEST COVERAGE REPORT\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            # Overall coverage
            if "totals" in coverage_data:
                totals = coverage_data["totals"]
                f.write("OVERALL COVERAGE\n")
                f.write("-" * 80 + "\n")
                f.write(f"Total Statements: {totals.get('num_statements', 0)}\n")
                f.write(f"Covered Statements: {totals.get('covered_lines', 0)}\n")
                f.write(f"Missing Statements: {totals.get('missing_lines', 0)}\n")

                coverage_percent = totals.get("percent_covered", 0)
                f.write(f"Coverage: {coverage_percent:.2f}%\n\n")

            # Per-file coverage
            if "files" in coverage_data:
                f.write("COVERAGE BY FILE\n")
                f.write("-" * 80 + "\n")

                files = coverage_data["files"]
                sorted_files = sorted(
                    files.items(),
                    key=lambda x: x[1].get("summary", {}).get("percent_covered", 0),
                    reverse=True,
                )

                for file_path, file_data in sorted_files:
                    summary = file_data.get("summary", {})
                    coverage = summary.get("percent_covered", 0)

                    f.write(f"\n{file_path}:\n")
                    f.write(f"  Coverage: {coverage:.2f}%\n")
                    f.write(f"  Statements: {summary.get('num_statements', 0)}\n")
                    f.write(f"  Covered: {summary.get('covered_lines', 0)}\n")
                    f.write(f"  Missing: {summary.get('missing_lines', 0)}\n")

            f.write("\n" + "=" * 80 + "\n")

        return output_file

    def generate_performance_report(
        self, performance_data: Dict[str, Any], output_file: Optional[Path] = None
    ) -> Path:
        """Generate performance test report."""
        if output_file is None:
            output_file = self.report_dir / "performance_test_report.txt"

        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("PERFORMANCE TEST REPORT\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            # Performance metrics
            if "metrics" in performance_data:
                f.write("PERFORMANCE METRICS\n")
                f.write("-" * 80 + "\n")

                metrics = performance_data["metrics"]
                for metric_name, metric_value in metrics.items():
                    f.write(f"{metric_name}: {metric_value}\n")

            # Test results
            if "results" in performance_data:
                f.write("\nTEST RESULTS\n")
                f.write("-" * 80 + "\n")

                results = performance_data["results"]
                for test_name, test_result in results.items():
                    f.write(f"\n{test_name}:\n")
                    f.write(f"  Status: {test_result.get('status', 'UNKNOWN')}\n")
                    f.write(f"  Duration: {test_result.get('duration', 0):.2f} seconds\n")

                    if "metrics" in test_result:
                        f.write("  Metrics:\n")
                        for metric, value in test_result["metrics"].items():
                            f.write(f"    {metric}: {value}\n")

            f.write("\n" + "=" * 80 + "\n")

        return output_file

    def generate_security_report(
        self, security_data: Dict[str, Any], output_file: Optional[Path] = None
    ) -> Path:
        """Generate security test report."""
        if output_file is None:
            output_file = self.report_dir / "security_test_report.txt"

        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("SECURITY TEST REPORT\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            # Security test results
            if "results" in security_data:
                f.write("SECURITY TEST RESULTS\n")
                f.write("-" * 80 + "\n")

                results = security_data["results"]
                for test_name, test_result in results.items():
                    f.write(f"\n{test_name}:\n")
                    f.write(f"  Status: {test_result.get('status', 'UNKNOWN')}\n")
                    f.write(f"  Severity: {test_result.get('severity', 'UNKNOWN')}\n")
                    f.write(f"  Description: {test_result.get('description', 'N/A')}\n")

            # Vulnerabilities
            if "vulnerabilities" in security_data:
                f.write("\nVULNERABILITIES\n")
                f.write("-" * 80 + "\n")

                vulnerabilities = security_data["vulnerabilities"]
                for vuln in vulnerabilities:
                    f.write(f"\n{vuln.get('name', 'Unknown')}:\n")
                    f.write(f"  Severity: {vuln.get('severity', 'UNKNOWN')}\n")
                    f.write(f"  Description: {vuln.get('description', 'N/A')}\n")
                    f.write(f"  Status: {vuln.get('status', 'UNKNOWN')}\n")

            f.write("\n" + "=" * 80 + "\n")

        return output_file

    def generate_comprehensive_report(
        self,
        execution_results: Dict[str, Any],
        coverage_data: Optional[Dict[str, Any]] = None,
        performance_data: Optional[Dict[str, Any]] = None,
        security_data: Optional[Dict[str, Any]] = None,
        output_file: Optional[Path] = None,
    ) -> Path:
        """Generate comprehensive report combining all test reports."""
        if output_file is None:
            output_file = self.report_dir / "comprehensive_test_report.txt"

        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("COMPREHENSIVE TEST REPORT\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            # Test execution summary
            f.write("1. TEST EXECUTION SUMMARY\n")
            f.write("=" * 80 + "\n")
            exec_report = self.generate_execution_report(execution_results)
            with open(exec_report, "r") as exec_f:
                f.write(exec_f.read())
            f.write("\n\n")

            # Coverage report
            if coverage_data:
                f.write("2. TEST COVERAGE REPORT\n")
                f.write("=" * 80 + "\n")
                cov_report = self.generate_coverage_report(coverage_data)
                with open(cov_report, "r") as cov_f:
                    f.write(cov_f.read())
                f.write("\n\n")

            # Performance report
            if performance_data:
                f.write("3. PERFORMANCE TEST REPORT\n")
                f.write("=" * 80 + "\n")
                perf_report = self.generate_performance_report(performance_data)
                with open(perf_report, "r") as perf_f:
                    f.write(perf_f.read())
                f.write("\n\n")

            # Security report
            if security_data:
                f.write("4. SECURITY TEST REPORT\n")
                f.write("=" * 80 + "\n")
                sec_report = self.generate_security_report(security_data)
                with open(sec_report, "r") as sec_f:
                    f.write(sec_f.read())
                f.write("\n\n")

            f.write("=" * 80 + "\n")
            f.write("END OF COMPREHENSIVE TEST REPORT\n")
            f.write("=" * 80 + "\n")

        return output_file


class CoverageAnalyzer:
    """Analyzes test coverage by module and feature."""

    def __init__(self, report_dir: Path):
        self.report_dir = report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def analyze_coverage_by_module(
        self, coverage_data: Dict[str, Any], output_file: Optional[Path] = None
    ) -> Path:
        """Analyze test coverage by module."""
        if output_file is None:
            output_file = self.report_dir / "coverage_analysis_by_module.txt"

        # Group files by module
        modules = {}

        if "files" in coverage_data:
            for file_path, file_data in coverage_data["files"].items():
                # Extract module name from file path
                parts = Path(file_path).parts
                module_name = "unknown"

                # Try to find module in hub/apps or services
                if "hub" in parts or "apps" in parts:
                    # Find the app name
                    try:
                        apps_idx = parts.index("apps")
                        if apps_idx + 1 < len(parts):
                            module_name = parts[apps_idx + 1]
                    except ValueError:
                        pass
                elif "services" in parts:
                    try:
                        services_idx = parts.index("services")
                        if services_idx + 1 < len(parts):
                            module_name = parts[services_idx + 1]
                    except ValueError:
                        pass

                if module_name not in modules:
                    modules[module_name] = {
                        "files": [],
                        "total_statements": 0,
                        "covered_statements": 0,
                        "missing_statements": 0,
                    }

                summary = file_data.get("summary", {})
                modules[module_name]["files"].append(file_path)
                modules[module_name]["total_statements"] += summary.get("num_statements", 0)
                modules[module_name]["covered_statements"] += summary.get("covered_lines", 0)
                modules[module_name]["missing_statements"] += summary.get("missing_lines", 0)

        # Generate report
        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("COVERAGE ANALYSIS BY MODULE\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            # Sort modules by coverage percentage
            sorted_modules = sorted(
                modules.items(),
                key=lambda x: (
                    x[1]["covered_statements"] / x[1]["total_statements"]
                    if x[1]["total_statements"] > 0
                    else 0
                ),
                reverse=True,
            )

            for module_name, module_data in sorted_modules:
                total = module_data["total_statements"]
                covered = module_data["covered_statements"]
                missing = module_data["missing_statements"]
                coverage = (covered / total * 100) if total > 0 else 0

                f.write(f"\n{module_name.upper()}:\n")
                f.write(f"  Coverage: {coverage:.2f}%\n")
                f.write(f"  Total Statements: {total}\n")
                f.write(f"  Covered: {covered}\n")
                f.write(f"  Missing: {missing}\n")
                f.write(f"  Files: {len(module_data['files'])}\n")

            f.write("\n" + "=" * 80 + "\n")

        return output_file

    def analyze_coverage_by_feature(
        self,
        coverage_data: Dict[str, Any],
        feature_mapping: Optional[Dict[str, List[str]]] = None,
        output_file: Optional[Path] = None,
    ) -> Path:
        """Analyze test coverage by feature."""
        if output_file is None:
            output_file = self.report_dir / "coverage_analysis_by_feature.txt"

        # Group files by feature
        features = {}

        if "files" in coverage_data:
            for file_path, file_data in coverage_data["files"].items():
                # Determine feature from file path or mapping
                feature_name = "other"

                if feature_mapping:
                    for feat, patterns in feature_mapping.items():
                        if any(pattern in file_path for pattern in patterns):
                            feature_name = feat
                            break
                else:
                    # Default feature detection based on path
                    path_lower = file_path.lower()
                    if "contract" in path_lower:
                        feature_name = "contracts"
                    elif "asset" in path_lower:
                        feature_name = "assets"
                    elif "marketplace" in path_lower:
                        feature_name = "marketplace"
                    elif "semantic" in path_lower:
                        feature_name = "semantic"
                    elif "dq" in path_lower or "quality" in path_lower:
                        feature_name = "data_quality"
                    elif "compliance" in path_lower:
                        feature_name = "compliance"
                    elif "transformation" in path_lower:
                        feature_name = "transformation"
                    elif "virtualization" in path_lower:
                        feature_name = "virtualization"

                if feature_name not in features:
                    features[feature_name] = {
                        "files": [],
                        "total_statements": 0,
                        "covered_statements": 0,
                        "missing_statements": 0,
                    }

                summary = file_data.get("summary", {})
                features[feature_name]["files"].append(file_path)
                features[feature_name]["total_statements"] += summary.get("num_statements", 0)
                features[feature_name]["covered_statements"] += summary.get("covered_lines", 0)
                features[feature_name]["missing_statements"] += summary.get("missing_lines", 0)

        # Generate report
        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("COVERAGE ANALYSIS BY FEATURE\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            # Sort features by coverage percentage
            sorted_features = sorted(
                features.items(),
                key=lambda x: (
                    x[1]["covered_statements"] / x[1]["total_statements"]
                    if x[1]["total_statements"] > 0
                    else 0
                ),
                reverse=True,
            )

            for feature_name, feature_data in sorted_features:
                total = feature_data["total_statements"]
                covered = feature_data["covered_statements"]
                missing = feature_data["missing_statements"]
                coverage = (covered / total * 100) if total > 0 else 0

                f.write(f"\n{feature_name.upper()}:\n")
                f.write(f"  Coverage: {coverage:.2f}%\n")
                f.write(f"  Total Statements: {total}\n")
                f.write(f"  Covered: {covered}\n")
                f.write(f"  Missing: {missing}\n")
                f.write(f"  Files: {len(feature_data['files'])}\n")

            f.write("\n" + "=" * 80 + "\n")

        return output_file

    def identify_coverage_gaps(
        self,
        coverage_data: Dict[str, Any],
        min_coverage_threshold: float = 80.0,
        output_file: Optional[Path] = None,
    ) -> Path:
        """Identify coverage gaps."""
        if output_file is None:
            output_file = self.report_dir / "coverage_gaps.txt"

        gaps = []

        if "files" in coverage_data:
            for file_path, file_data in coverage_data["files"].items():
                summary = file_data.get("summary", {})
                coverage = summary.get("percent_covered", 0)

                if coverage < min_coverage_threshold:
                    gaps.append(
                        {
                            "file": file_path,
                            "coverage": coverage,
                            "statements": summary.get("num_statements", 0),
                            "missing": summary.get("missing_lines", 0),
                        }
                    )

        # Generate report
        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("COVERAGE GAPS ANALYSIS\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write(f"Minimum Coverage Threshold: {min_coverage_threshold}%\n\n")

            if not gaps:
                f.write("✅ No coverage gaps found (all files meet the threshold)\n")
            else:
                f.write(f"Found {len(gaps)} file(s) below threshold:\n\n")

                # Sort by coverage (lowest first)
                gaps.sort(key=lambda x: x["coverage"])

                for gap in gaps:
                    f.write(f"{gap['file']}:\n")
                    f.write(f"  Coverage: {gap['coverage']:.2f}%\n")
                    f.write(f"  Statements: {gap['statements']}\n")
                    f.write(f"  Missing: {gap['missing']}\n\n")

            f.write("=" * 80 + "\n")

        return output_file

    def generate_coverage_recommendations(
        self, coverage_data: Dict[str, Any], output_file: Optional[Path] = None
    ) -> Path:
        """Generate coverage improvement recommendations."""
        if output_file is None:
            output_file = self.report_dir / "coverage_recommendations.txt"

        recommendations = []

        # Analyze coverage data and generate recommendations
        if "files" in coverage_data:
            low_coverage_files = []
            high_priority_files = []

            for file_path, file_data in coverage_data["files"].items():
                summary = file_data.get("summary", {})
                coverage = summary.get("percent_covered", 0)
                missing = summary.get("missing_lines", 0)

                if coverage < 50:
                    low_coverage_files.append((file_path, coverage, missing))

                # High priority: critical modules with low coverage
                if (
                    any(
                        keyword in file_path.lower()
                        for keyword in [
                            "auth",
                            "security",
                            "payment",
                            "api",
                            "contract",
                            "normalize",
                        ]
                    )
                    and coverage < 80
                ):
                    high_priority_files.append((file_path, coverage, missing))

            if low_coverage_files:
                recommendations.append(
                    {
                        "priority": "HIGH",
                        "category": "Low Coverage Files",
                        "description": f"Found {len(low_coverage_files)} files with coverage below 50%",
                        "action": "Add unit tests for these files to improve coverage",
                        "files": low_coverage_files[:10],  # Top 10
                    }
                )

            if high_priority_files:
                recommendations.append(
                    {
                        "priority": "CRITICAL",
                        "category": "Critical Module Coverage",
                        "description": f"Found {len(high_priority_files)} critical modules with low coverage",
                        "action": "Prioritize adding tests for these critical modules",
                        "files": high_priority_files[:10],  # Top 10
                    }
                )

        # Generate report
        with open(output_file, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("COVERAGE IMPROVEMENT RECOMMENDATIONS\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            if not recommendations:
                f.write("✅ No specific recommendations at this time.\n")
                f.write("Coverage appears to be adequate.\n")
            else:
                for rec in recommendations:
                    f.write(f"\n{rec['priority']} PRIORITY: {rec['category']}\n")
                    f.write("-" * 80 + "\n")
                    f.write(f"Description: {rec['description']}\n")
                    f.write(f"Action: {rec['action']}\n")
                    f.write(f"\nAffected Files:\n")
                    for file_path, coverage, missing in rec["files"]:
                        f.write(
                            f"  - {file_path} (Coverage: {coverage:.2f}%, Missing: {missing} lines)\n"
                        )

            f.write("\n" + "=" * 80 + "\n")

        return output_file


if __name__ == "__main__":
    # Example usage
    report_dir = Path("test_reports")
    generator = TestReportGenerator(report_dir)
    analyzer = CoverageAnalyzer(report_dir)

    print("Test reporting modules initialized.")
    print(f"Report directory: {report_dir}")
