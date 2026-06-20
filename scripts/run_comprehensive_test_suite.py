#!/usr/bin/env python3
"""
Comprehensive Test Suite Runner

Orchestrates the complete test execution, reporting, and validation process:
1. Executes all test types (unit, integration, E2E, performance, security)
2. Generates comprehensive reports
3. Validates test results and coverage requirements
4. Analyzes coverage by module and feature
5. Generates coverage improvement recommendations

Usage:
    python scripts/run_comprehensive_test_suite.py [--test-type TYPE] [--coverage] [--report-dir DIR]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import our modules
from scripts.run_comprehensive_test_execution import PROJECT_ROOT as EXEC_PROJECT_ROOT
from scripts.run_comprehensive_test_execution import TestExecutor
from scripts.test_reporting import CoverageAnalyzer, TestReportGenerator
from scripts.test_validation import TestValidator

# Use the same project root
PROJECT_ROOT = EXEC_PROJECT_ROOT


def find_python_executable() -> str:
    """Find Python executable."""
    import sys

    # Try to find virtual environment
    VENV_PATHS = [
        PROJECT_ROOT / "venv",
        PROJECT_ROOT / "venv-python312-test",
    ]

    python_executable = sys.executable

    for venv_path in VENV_PATHS:
        venv_python = venv_path / "bin" / "python3"
        if venv_python.exists():
            python_executable = str(venv_python)
            print(f"Using Python from virtual environment: {python_executable}")
            break

    return python_executable


def load_coverage_data(report_dir: Path, test_type: str) -> dict[str, Any] | None:
    """Load coverage data from JSON file."""
    coverage_file = report_dir / f"coverage_{test_type}.json"
    if coverage_file.exists():
        try:
            with open(coverage_file) as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load coverage data from {coverage_file}: {e}")
    return None


def aggregate_coverage_data(report_dir: Path, test_types: list) -> dict[str, Any] | None:
    """Aggregate coverage data from multiple test types."""
    all_coverage: dict[str, Any] = {}

    for test_type in test_types:
        coverage_data = load_coverage_data(report_dir, test_type)
        if coverage_data:
            # Merge coverage data
            if "files" in coverage_data:
                if "files" not in all_coverage:
                    all_coverage["files"] = {}
                all_coverage["files"].update(coverage_data["files"])

            if "totals" in coverage_data:
                # Aggregate totals
                if "totals" not in all_coverage:
                    all_coverage["totals"] = {
                        "num_statements": 0,
                        "covered_lines": 0,
                        "missing_lines": 0,
                    }

                totals = coverage_data["totals"]
                all_coverage["totals"]["num_statements"] = int(
                    all_coverage["totals"]["num_statements"]
                ) + int(totals.get("num_statements", 0))
                all_coverage["totals"]["covered_lines"] = int(
                    all_coverage["totals"]["covered_lines"]
                ) + int(totals.get("covered_lines", 0))
                all_coverage["totals"]["missing_lines"] = int(
                    all_coverage["totals"]["missing_lines"]
                ) + int(totals.get("missing_lines", 0))

    # Calculate overall coverage percentage
    if "totals" in all_coverage:
        totals = all_coverage["totals"]
        total_statements = totals["num_statements"]
        covered_statements = totals["covered_lines"]

        if total_statements > 0:
            # Calculate coverage percentage (float value in dict with mixed types)
            percent_covered = covered_statements / total_statements * 100
            all_coverage["totals"]["percent_covered"] = percent_covered  # type: ignore[assignment]

    return all_coverage if all_coverage else None


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Comprehensive Test Suite Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--test-type",
        choices=["unit", "integration", "e2e", "performance", "security", "all"],
        default="all",
        help="Test type to execute (default: all)",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage reports",
    )
    parser.add_argument(
        "--report-dir",
        type=str,
        default="test_reports",
        help="Directory for test reports (default: test_reports)",
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=80.0,
        help="Minimum coverage threshold (default: 80.0)",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("COMPREHENSIVE TEST SUITE RUNNER")
    print("=" * 80)
    print("\nFollowing engineering best practices:")
    print("  - No mocks/stubs - uses real implementations")
    print("  - Fixes root causes, not symptoms")
    print("  - Comprehensive test coverage")
    print("  - Follows DRY, SOLID, and clean code principles")
    print()

    # Determine test types to run
    if args.test_type == "all":
        test_types = ["unit", "integration", "e2e", "performance", "security"]
    else:
        test_types = [args.test_type]

    # Create report directory
    report_dir = PROJECT_ROOT / args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    # Find Python executable
    python_executable = find_python_executable()

    # Step 1: Execute tests
    print("=" * 80)
    print("STEP 1: EXECUTING TESTS")
    print("=" * 80)
    print()

    executor = TestExecutor(PROJECT_ROOT, python_executable, report_dir)
    results = executor.execute_all_tests(test_types=test_types, with_coverage=args.coverage)

    # Save execution results
    results_json = {
        "timestamp": datetime.now().isoformat(),
        "test_types": test_types,
        "with_coverage": args.coverage,
        "results": {k: v.to_dict() for k, v in results.items()},
    }

    results_file = report_dir / "test_execution_results.json"
    with open(results_file, "w") as f:
        json.dump(results_json, f, indent=2)

    print(f"\nTest execution results saved to: {results_file}")

    # Step 2: Generate reports
    print("\n" + "=" * 80)
    print("STEP 2: GENERATING REPORTS")
    print("=" * 80)
    print()

    report_generator = TestReportGenerator(report_dir)

    # Generate execution report
    execution_results = {k: v.to_dict() for k, v in results.items()}
    exec_report = report_generator.generate_execution_report(execution_results)
    print(f"✅ Test execution report: {exec_report}")

    # Aggregate and generate coverage reports if available
    coverage_data = None
    if args.coverage:
        coverage_data = aggregate_coverage_data(report_dir, test_types)

        if coverage_data:
            cov_report = report_generator.generate_coverage_report(coverage_data)
            print(f"✅ Test coverage report: {cov_report}")

    # Generate performance report (if performance tests were run)
    performance_data = {}
    if "performance" in results and results["performance"].status != "SKIPPED":
        # Extract performance metrics from results
        performance_data = {
            "results": {
                "performance_tests": {
                    "status": results["performance"].status,
                    "duration": results["performance"].duration,
                }
            }
        }
        perf_report = report_generator.generate_performance_report(performance_data)
        print(f"✅ Performance test report: {perf_report}")

    # Generate security report (if security tests were run)
    security_data = {}
    if "security" in results and results["security"].status != "SKIPPED":
        security_data = {
            "results": {
                "security_tests": {
                    "status": results["security"].status,
                    "duration": results["security"].duration,
                }
            }
        }
        sec_report = report_generator.generate_security_report(security_data)
        print(f"✅ Security test report: {sec_report}")

    # Generate comprehensive report
    comprehensive_report = report_generator.generate_comprehensive_report(
        execution_results,
        coverage_data=coverage_data,
        performance_data=performance_data if performance_data else None,
        security_data=security_data if security_data else None,
    )
    print(f"✅ Comprehensive test report: {comprehensive_report}")

    # Step 3: Coverage analysis
    if args.coverage and coverage_data:
        print("\n" + "=" * 80)
        print("STEP 3: COVERAGE ANALYSIS")
        print("=" * 80)
        print()

        analyzer = CoverageAnalyzer(report_dir)

        # Analyze by module
        module_analysis = analyzer.analyze_coverage_by_module(coverage_data)
        print(f"✅ Coverage analysis by module: {module_analysis}")

        # Analyze by feature
        feature_analysis = analyzer.analyze_coverage_by_feature(coverage_data)
        print(f"✅ Coverage analysis by feature: {feature_analysis}")

        # Identify gaps
        gaps_analysis = analyzer.identify_coverage_gaps(
            coverage_data, min_coverage_threshold=args.min_coverage
        )
        print(f"✅ Coverage gaps analysis: {gaps_analysis}")

        # Generate recommendations
        recommendations = analyzer.generate_coverage_recommendations(coverage_data)
        print(f"✅ Coverage recommendations: {recommendations}")

    # Step 4: Validate results
    print("\n" + "=" * 80)
    print("STEP 4: VALIDATING RESULTS")
    print("=" * 80)
    print()

    validator = TestValidator(report_dir)

    # Validate test results
    all_tests_valid, _test_validation = validator.validate_test_results(execution_results)
    print("✅ Test validation report generated")

    # Validate coverage requirements
    coverage_valid = True
    if args.coverage and coverage_data:
        coverage_valid, _coverage_validation = validator.validate_coverage_requirements(
            coverage_data, min_coverage=args.min_coverage
        )
        print("✅ Coverage validation report generated")

    # Validate performance targets
    perf_valid = True
    if performance_data:
        perf_valid, _perf_validation = validator.validate_performance_targets(performance_data)
        print("✅ Performance validation report generated")

    # Validate security requirements
    sec_valid = True
    if security_data:
        sec_valid, _sec_validation = validator.validate_security_requirements(security_data)
        print("✅ Security validation report generated")

    # Final summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print()

    total_tests = sum(r.total_tests for r in results.values())
    total_passed = sum(r.passed for r in results.values())
    total_failed = sum(r.failed for r in results.values())
    total_errors = sum(r.errors for r in results.values())

    print("Test Execution:")
    print(f"  Total Tests: {total_tests}")
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    print(f"  Errors: {total_errors}")
    print()

    print("Validation Results:")
    print(f"  All Tests Passing: {'✅ YES' if all_tests_valid else '❌ NO'}")
    if args.coverage:
        print(f"  Coverage Requirements Met: {'✅ YES' if coverage_valid else '❌ NO'}")
    if performance_data:
        print(f"  Performance Targets Met: {'✅ YES' if perf_valid else '❌ NO'}")
    if security_data:
        print(f"  Security Requirements Met: {'✅ YES' if sec_valid else '❌ NO'}")
    print()

    print(f"Reports generated in: {report_dir}")
    print()

    # Determine overall success
    overall_success = (
        all_tests_valid
        and (coverage_valid if args.coverage else True)
        and (perf_valid if performance_data else True)
        and (sec_valid if security_data else True)
    )

    if overall_success:
        print("=" * 80)
        print("✅ ALL TESTS PASSED AND REQUIREMENTS MET")
        print("=" * 80)
        return 0
    else:
        print("=" * 80)
        print("❌ SOME TESTS FAILED OR REQUIREMENTS NOT MET")
        print("=" * 80)
        print("\nPlease review the reports and fix any issues.")
        print("Remember: Fix root causes, not symptoms. No mocks/stubs.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
