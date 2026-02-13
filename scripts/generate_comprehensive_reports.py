#!/usr/bin/env python3
"""
Generate Comprehensive Test Reports

Generates all required reports after test execution:
- Test execution report
- Coverage reports (unit, integration, E2E)
- Performance test report
- Security test report
- Coverage analysis and recommendations
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

REPORT_DIR = PROJECT_ROOT / "test_reports_comprehensive"


def load_test_results() -> Dict[str, Any]:
    """Load test execution results from JSON files or parse log files"""
    results = {}

    # Look for test execution results
    result_files = list(REPORT_DIR.glob("test_execution_results*.json"))
    if result_files:
        latest = max(result_files, key=lambda p: p.stat().st_mtime)
        with open(latest) as f:
            results = json.load(f)
    else:
        # Parse log files if JSON not available
        results = parse_log_files()

    return results


def parse_log_files() -> Dict[str, Any]:
    """Parse test execution results from log files"""
    results = {"results": {}}

    # Parse comprehensive test log
    comp_logs = list(Path("/tmp").glob("comprehensive_tests_*.log"))
    if comp_logs:
        latest_log = max(comp_logs, key=lambda p: p.stat().st_mtime)
        results.update(parse_comprehensive_log(latest_log))

    # Parse individual test type logs
    unit_logs = list(Path("/tmp").glob("unit_*_*.log"))
    integration_logs = list(Path("/tmp").glob("integration_tests_*.log"))
    e2e_logs = list(Path("/tmp").glob("e2e_tests_*.log"))
    perf_logs = list(Path("/tmp").glob("performance_tests_*.log"))
    security_logs = list(Path("/tmp").glob("security_tests_*.log"))

    if unit_logs:
        results["results"]["unit"] = parse_unit_tests(unit_logs)
    if integration_logs:
        results["results"]["integration"] = parse_test_log(
            max(integration_logs, key=lambda p: p.stat().st_mtime)
        )
    if e2e_logs:
        results["results"]["e2e"] = parse_test_log(max(e2e_logs, key=lambda p: p.stat().st_mtime))
    if perf_logs:
        results["results"]["performance"] = parse_test_log(
            max(perf_logs, key=lambda p: p.stat().st_mtime)
        )
    if security_logs:
        results["results"]["security"] = parse_test_log(
            max(security_logs, key=lambda p: p.stat().st_mtime)
        )

    return results


def parse_comprehensive_log(log_file: Path) -> Dict[str, Any]:
    """Parse comprehensive test suite log file"""
    results = {}

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Extract phase summaries
        if "Phase 1 Summary" in content:
            # Parse unit tests summary
            pass

        # Extract final summary
        if "FINAL SUMMARY" in content:
            # Parse final summary
            pass

    except Exception as e:
        print(f"Error parsing comprehensive log: {e}")

    return results


def parse_unit_tests(log_files: List[Path]) -> Dict[str, Any]:
    """Parse unit test log files"""
    total_tests = 0
    passed = 0
    failed = 0
    errors = 0
    skipped = 0

    for log_file in log_files:
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Extract test counts
            import re

            ran_match = re.search(r"Ran (\d+) test", content)
            if ran_match:
                total_tests += int(ran_match.group(1))

            ok_match = re.search(r"OK", content)
            if ok_match:
                passed += 1

            failed_match = re.search(r"FAILED.*failures=(\d+)", content)
            if failed_match:
                failed += int(failed_match.group(1))

            error_match = re.search(r"ERROR.*errors=(\d+)", content)
            if error_match:
                errors += int(error_match.group(1))

        except Exception:
            pass

    return {
        "total_tests": total_tests,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "success": failed == 0 and errors == 0,
    }


def parse_test_log(log_file: Path) -> Dict[str, Any]:
    """Parse a test log file for summary statistics"""
    total_tests = 0
    passed = 0
    failed = 0
    errors = 0
    skipped = 0

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        import re

        # Extract test counts
        ran_match = re.search(r"Ran (\d+) test", content)
        if ran_match:
            total_tests = int(ran_match.group(1))

        failed_match = re.search(r"FAILED.*failures=(\d+)", content)
        if failed_match:
            failed = int(failed_match.group(1))

        error_match = re.search(r"ERROR.*errors=(\d+)", content)
        if error_match:
            errors = int(error_match.group(1))

        skipped_match = re.search(r"skipped=(\d+)", content)
        if skipped_match:
            skipped = int(skipped_match.group(1))

        passed = total_tests - failed - errors - skipped

    except Exception as e:
        print(f"Error parsing test log {log_file}: {e}")

    return {
        "total_tests": total_tests,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "success": failed == 0 and errors == 0,
    }


def generate_execution_report(results: Dict[str, Any]) -> str:
    """Generate test execution report"""
    report = []
    report.append("# Comprehensive Test Execution Report")
    report.append("")
    report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    if not results:
        report.append("No test results found.")
        return "\n".join(report)

    # Overall summary
    report.append("## Overall Summary")
    report.append("")

    total_tests = 0
    total_passed = 0
    total_failed = 0
    total_errors = 0
    total_skipped = 0

    for test_type, data in results.get("results", {}).items():
        total_tests += data.get("total_tests", 0)
        total_passed += data.get("passed", 0)
        total_failed += data.get("failed", 0)
        total_errors += data.get("errors", 0)
        total_skipped += data.get("skipped", 0)

    report.append(f"- **Total Tests**: {total_tests}")
    report.append(f"- **Passed**: {total_passed}")
    report.append(f"- **Failed**: {total_failed}")
    report.append(f"- **Errors**: {total_errors}")
    report.append(f"- **Skipped**: {total_skipped}")
    report.append("")

    # Per-type breakdown
    report.append("## Test Type Breakdown")
    report.append("")
    report.append("| Test Type | Status | Tests | Passed | Failed | Errors | Skipped | Duration |")
    report.append("|-----------|--------|-------|--------|--------|--------|---------|----------|")

    for test_type, data in results.get("results", {}).items():
        status = "✅ PASSED" if data.get("success") else "❌ FAILED"
        duration = f"{data.get('duration', 0):.1f}s"
        report.append(
            f"| {test_type} | {status} | {data.get('total_tests', 0)} | "
            f"{data.get('passed', 0)} | {data.get('failed', 0)} | "
            f"{data.get('errors', 0)} | {data.get('skipped', 0)} | {duration} |"
        )

    report.append("")

    return "\n".join(report)


def generate_coverage_report() -> str:
    """Generate coverage report"""
    report = []
    report.append("# Test Coverage Report")
    report.append("")
    report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    # Look for coverage files
    coverage_files = list(REPORT_DIR.glob("coverage_*.json"))

    if not coverage_files:
        report.append("No coverage data found.")
        report.append("")
        report.append("To generate coverage reports, run tests with coverage enabled:")
        report.append("```bash")
        report.append(
            "pytest --cov=hub --cov-report=json:test_reports_comprehensive/coverage_unit.json"
        )
        report.append("```")
        return "\n".join(report)

    report.append("## Coverage Summary")
    report.append("")

    for cov_file in coverage_files:
        test_type = cov_file.stem.replace("coverage_", "")
        report.append(f"### {test_type.title()} Tests Coverage")
        report.append("")

        try:
            with open(cov_file) as f:
                cov_data = json.load(f)

            totals = cov_data.get("totals", {})
            percent = totals.get("percent_covered", 0)
            lines = totals.get("covered_lines", 0)
            total_lines = totals.get("num_statements", 0)

            report.append(f"- **Coverage**: {percent:.2f}%")
            report.append(f"- **Lines Covered**: {lines}/{total_lines}")
            report.append("")
        except Exception as e:
            report.append(f"Error reading coverage file: {e}")
            report.append("")

    return "\n".join(report)


def generate_performance_report() -> str:
    """Generate performance test report"""
    report = []
    report.append("# Performance Test Report")
    report.append("")
    report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    # Look for performance test logs
    perf_logs = list(Path("/tmp").glob("performance_tests_*.log"))

    if not perf_logs:
        report.append("No performance test data found.")
        return "\n".join(report)

    latest_log = max(perf_logs, key=lambda p: p.stat().st_mtime)
    report.append(f"**Log File**: {latest_log}")
    report.append("")
    report.append("Performance test results are available in the log file.")
    report.append("")

    return "\n".join(report)


def generate_security_report() -> str:
    """Generate security test report"""
    report = []
    report.append("# Security Test Report")
    report.append("")
    report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    # Look for security test logs
    security_logs = list(Path("/tmp").glob("security_tests_*.log"))

    if not security_logs:
        report.append("No security test data found.")
        return "\n".join(report)

    latest_log = max(security_logs, key=lambda p: p.stat().st_mtime)
    report.append(f"**Log File**: {latest_log}")
    report.append("")
    report.append("Security test results are available in the log file.")
    report.append("")

    return "\n".join(report)


def generate_coverage_analysis() -> str:
    """Generate coverage analysis and recommendations"""
    report = []
    report.append("# Test Coverage Analysis")
    report.append("")
    report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    report.append("## Coverage by Module")
    report.append("")
    report.append("(Analysis will be generated from coverage data)")
    report.append("")

    report.append("## Coverage by Feature")
    report.append("")
    report.append("(Analysis will be generated from coverage data)")
    report.append("")

    report.append("## Coverage Gaps")
    report.append("")
    report.append("(Gaps will be identified from coverage data)")
    report.append("")

    report.append("## Improvement Recommendations")
    report.append("")
    report.append("(Recommendations will be generated based on coverage analysis)")
    report.append("")

    return "\n".join(report)


def main():
    """Generate all comprehensive reports"""
    print("Generating comprehensive test reports...")
    print("")

    # Ensure report directory exists
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Load test results
    results = load_test_results()

    # Generate reports
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("1. Generating execution report...")
    execution_report = generate_execution_report(results)
    exec_file = REPORT_DIR / f"EXECUTION_REPORT_{timestamp}.md"
    exec_file.write_text(execution_report)
    print(f"   ✅ Saved to: {exec_file}")

    print("2. Generating coverage report...")
    coverage_report = generate_coverage_report()
    cov_file = REPORT_DIR / f"COVERAGE_REPORT_{timestamp}.md"
    cov_file.write_text(coverage_report)
    print(f"   ✅ Saved to: {cov_file}")

    print("3. Generating performance report...")
    perf_report = generate_performance_report()
    perf_file = REPORT_DIR / f"PERFORMANCE_REPORT_{timestamp}.md"
    perf_file.write_text(perf_report)
    print(f"   ✅ Saved to: {perf_file}")

    print("4. Generating security report...")
    sec_report = generate_security_report()
    sec_file = REPORT_DIR / f"SECURITY_REPORT_{timestamp}.md"
    sec_file.write_text(sec_report)
    print(f"   ✅ Saved to: {sec_file}")

    print("5. Generating coverage analysis...")
    analysis_report = generate_coverage_analysis()
    analysis_file = REPORT_DIR / f"COVERAGE_ANALYSIS_{timestamp}.md"
    analysis_file.write_text(analysis_report)
    print(f"   ✅ Saved to: {analysis_file}")

    print("")
    print("✅ All reports generated successfully!")
    print("")
    print(f"Reports saved to: {REPORT_DIR}")


if __name__ == "__main__":
    main()
