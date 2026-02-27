#!/usr/bin/env python3
"""
Generate Test Summary Report

Generates a comprehensive test summary report from collected evidence.
Reads test results, coverage data, performance metrics, and security scans
from test_reports_comprehensive/{date}/ directories and generates a formatted
report using the TEST_SUMMARY_REPORT_TEMPLATE.md template.

Usage:
    python3 scripts/generate_test_summary_report.py \\
        [--date YYYY-MM-DD] [--output OUTPUT_FILE.md]
"""

import argparse
import json
import platform
import re
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Constants
REPORT_DIR = PROJECT_ROOT / "test_reports_comprehensive"
TEMPLATE_FILE = PROJECT_ROOT / "docs" / "TEST_SUMMARY_REPORT_TEMPLATE.md"
FEATURES_FILE = PROJECT_ROOT / "docs" / "FEATURES.md"
USE_CASES_FILE = PROJECT_ROOT / "docs" / "USE_CASES.md"
USER_JOURNEYS_FILE = PROJECT_ROOT / "docs" / "USER_JOURNEYS.md"

# Feature list (29 features)
FEATURES = [
    "Auth",
    "Contracts",
    "ODPS",
    "Assets",
    "Datasets",
    "Data Quality",
    "Compliance",
    "Marketplace",
    "Governance",
    "Search",
    "Observability",
    "Workflows",
    "Lineage",
    "Versioning",
    "BaaS",
    "Integrations",
    "Jobs",
    "Files",
    "Semantic",
    "AI",
    "ML",
    "Social",
    "Data Mesh",
    "Virtualization",
    "Scheduled Ingestion",
    "Scheduled Export",
    "Webhooks",
    "Audit",
    "Health",
]

# Test categories (smoke after backend per Phase 4.1b)
TEST_CATEGORIES = [
    "unit",
    "integration",
    "e2e",
    "uc_journey_persona",
    "smoke",
    "security",
    "performance",
    "concurrency",
    "regression",
    "frontend-unit",
    "frontend-e2e",
]


class TestSummaryReportGenerator:
    """Generates comprehensive test summary reports from collected evidence."""

    def __init__(self, date: Optional[str] = None, output_file: Optional[Path] = None):
        """Initialize report generator.

        Args:
            date: Date string (YYYY-MM-DD) or None to use latest
            output_file: Output file path or None for auto-generated name
        """
        self.date = date or self._get_latest_date()
        self.report_dir = REPORT_DIR / self.date
        self.output_file = output_file or self._get_output_file()
        self.template = self._load_template()
        self.data: Dict[str, Any] = {}
        self.use_cases: List[str] = []
        self.journeys: List[str] = []
        self.test_to_feature_map: Dict[str, str] = {}
        self.test_to_use_case_map: Dict[str, str] = {}
        self.test_to_journey_map: Dict[str, str] = {}

    def _get_latest_date(self) -> str:
        """Get the latest date directory."""
        if not REPORT_DIR.exists():
            raise FileNotFoundError(f"Report directory not found: {REPORT_DIR}")

        date_dirs = [
            d.name
            for d in REPORT_DIR.iterdir()
            if d.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}", d.name)
        ]
        if not date_dirs:
            raise FileNotFoundError(f"No date directories found in {REPORT_DIR}")

        return max(date_dirs)

    def _get_output_file(self) -> Path:
        """Generate output file path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return REPORT_DIR / self.date / f"TEST_SUMMARY_REPORT_{timestamp}.md"

    def _load_template(self) -> str:
        """Load the report template."""
        if not TEMPLATE_FILE.exists():
            raise FileNotFoundError(f"Template file not found: {TEMPLATE_FILE}")

        return TEMPLATE_FILE.read_text()

    def _load_json_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load JSON file safely."""
        if not file_path.exists():
            return None

        try:
            return json.loads(file_path.read_text())
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️  Warning: Could not load {file_path}: {e}")
            return None

    def _load_summary(self) -> Optional[Dict[str, Any]]:
        """Load summary.json from report directory."""
        summary_file = self.report_dir / "summary.json"
        return self._load_json_file(summary_file)

    def _parse_junit_xml(self, path: Path) -> Optional[Dict[str, Any]]:
        """Parse JUnit XML to get total, passed, failed, skipped, errors, duration.
        Used when evidence comes from Phase 12A scripts (junit.xml per category).
        """
        if not path.exists():
            return None
        try:
            tree = ElementTree.parse(path)
            root = tree.getroot()
            total = 0
            failed = 0
            errors = 0
            skipped = 0
            duration = 0.0
            for elem in root.iter():
                # Support namespaced tags (e.g. {http://...}testsuite) by using local name
                local_tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if local_tag in ("testsuite", "testsuites"):
                    total += int(elem.get("tests", 0))
                    failed += int(elem.get("failures", 0))
                    errors += int(elem.get("errors", 0))
                    skipped += int(elem.get("skipped", 0))
                    t = elem.get("time")
                    if t is not None:
                        try:
                            duration += float(t)
                        except ValueError:
                            pass
            passed = max(0, total - failed - errors - skipped)
            return {
                "summary": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "skipped": skipped,
                    "errors": errors,
                    "duration": round(duration, 2),
                }
            }
        except Exception as e:
            print(f"⚠️  Warning: Could not parse JUnit XML {path}: {e}")
            return None

    def _load_phase_12a_evidence(self) -> bool:
        """Load Phase 12A evidence (phase_12a_1_summary.json, phase_12a_3_summary.json)
        and JUnit XML per category. Populates self.data['test_results'] and self.data['summary'].
        Returns True if Phase 12A evidence was found and loaded.
        """
        p12a_1 = self.report_dir / "phase_12a_1_summary.json"
        p12a_3 = self.report_dir / "phase_12a_3_summary.json"
        if not p12a_1.exists() and not p12a_3.exists():
            return False

        self.data["test_results"] = {}
        total_all = 0
        passed_all = 0
        failed_all = 0
        skipped_all = 0
        errors_all = 0
        duration_all = 0.0

        # Backend: unit, integration, e2e, uc_journey_persona (from phase_12a_1_summary.json)
        for category in ("unit", "integration", "e2e", "uc_journey_persona"):
            junit_path = self.report_dir / category / "junit.xml"
            results = self._parse_junit_xml(junit_path)
            if results:
                self.data["test_results"][category] = results
                s = results["summary"]
                total_all += s["total"]
                passed_all += s["passed"]
                failed_all += s["failed"]
                skipped_all += s["skipped"]
                errors_all += s["errors"]
                duration_all += s["duration"]
            elif p12a_1.exists():
                raw = self._load_json_file(p12a_1)
                if raw and category in raw and isinstance(raw[category], dict):
                    exit_code = raw[category].get("exit_code", -1)
                    dur = raw[category].get("duration_seconds", 0) or 0
                    # Infer minimal summary from exit code (no per-test counts)
                    self.data["test_results"][category] = {
                        "summary": {
                            "total": 1,
                            "passed": 1 if exit_code == 0 else 0,
                            "failed": 0 if exit_code == 0 else 1,
                            "skipped": 0,
                            "errors": 0,
                            "duration": float(dur),
                        }
                    }
                    total_all += 1
                    if exit_code == 0:
                        passed_all += 1
                    else:
                        failed_all += 1
                    duration_all += float(dur)

        # Smoke (12A.1.5, Phase 4.1b): JUnit only from run_phase_12a_full_suites.sh
        smoke_junit = self.report_dir / "smoke" / "junit.xml"
        smoke_results = self._parse_junit_xml(smoke_junit)
        if smoke_results:
            self.data["test_results"]["smoke"] = smoke_results
            s = smoke_results["summary"]
            total_all += s["total"]
            passed_all += s["passed"]
            failed_all += s["failed"]
            skipped_all += s["skipped"]
            errors_all += s["errors"]
            duration_all += s["duration"]

        # 12A.3: security, performance, concurrency, regression
        for category in ("security", "performance", "concurrency", "regression"):
            junit_path = self.report_dir / category / "junit.xml"
            results = self._parse_junit_xml(junit_path)
            if results:
                self.data["test_results"][category] = results
                s = results["summary"]
                total_all += s["total"]
                passed_all += s["passed"]
                failed_all += s["failed"]
                skipped_all += s["skipped"]
                errors_all += s["errors"]
                duration_all += s["duration"]
            elif p12a_3.exists():
                raw = self._load_json_file(p12a_3)
                if raw and not raw.get("skipped") and category in raw and isinstance(raw[category], dict):
                    exit_code = raw[category].get("exit_code", -1)
                    # No duration in phase_12a_3_summary by default; use 0
                    self.data["test_results"][category] = {
                        "summary": {
                            "total": 1,
                            "passed": 1 if exit_code == 0 else 0,
                            "failed": 0 if exit_code == 0 else 1,
                            "skipped": 0,
                            "errors": 0,
                            "duration": 0.0,
                        }
                    }
                    total_all += 1
                    if exit_code == 0:
                        passed_all += 1
                    else:
                        failed_all += 1

        # Frontend: frontend-unit, frontend-e2e (logs only in Phase 12A; try JUnit if present)
        for category in ("frontend-unit", "frontend-e2e"):
            junit_path = self.report_dir / category / "junit.xml"
            results = self._parse_junit_xml(junit_path)
            if results:
                self.data["test_results"][category] = results
                s = results["summary"]
                total_all += s["total"]
                passed_all += s["passed"]
                failed_all += s["failed"]
                skipped_all += s["skipped"]
                errors_all += s["errors"]
                duration_all += s["duration"]
            else:
                # No JUnit; leave category absent or with zeros (template will show 0)
                self.data["test_results"][category] = {
                    "summary": {
                        "total": 0,
                        "passed": 0,
                        "failed": 0,
                        "skipped": 0,
                        "errors": 0,
                        "duration": 0.0,
                    }
                }

        self.data["summary"] = {
            "total": total_all,
            "passed": passed_all,
            "failed": failed_all,
            "skipped": skipped_all,
            "errors": errors_all,
            "duration": duration_all,
        }
        return True

    def _load_test_results(self, test_type: str) -> Optional[Dict[str, Any]]:
        """Load test results for a specific test type.

        Tries results.json first; if not found, tries junit.xml (e.g. from
        standalone run_uc_journey_persona_tests.sh or other category scripts).
        """
        results_file = self.report_dir / test_type / "results.json"
        results = self._load_json_file(results_file)
        if results:
            return results
        junit_path = self.report_dir / test_type / "junit.xml"
        return self._parse_junit_xml(junit_path)

    def _load_coverage_data(self) -> Optional[Dict[str, Any]]:
        """Load coverage data from coverage.json."""
        coverage_file = self.report_dir / "coverage.json"
        return self._load_json_file(coverage_file)

    def _load_performance_metrics(self) -> Optional[Dict[str, Any]]:
        """Load performance metrics from CSV or JSON."""
        perf_dir = self.report_dir / "performance"
        metrics_file = perf_dir / "metrics.csv"
        if metrics_file.exists():
            # Parse CSV (simplified - could use csv module for full parsing)
            return self._parse_performance_csv(metrics_file)

        metrics_json = perf_dir / "metrics.json"
        return self._load_json_file(metrics_json)

    def _parse_performance_csv(self, csv_file: Path) -> Dict[str, Any]:
        """Parse performance metrics CSV file."""
        metrics: Dict[str, Any] = {}
        try:
            lines = csv_file.read_text().strip().split("\n")
            if len(lines) < 2:
                return metrics

            headers = [h.strip() for h in lines[0].split(",")]
            for line in lines[1:]:
                values = [v.strip() for v in line.split(",")]
                if len(values) == len(headers):
                    row = dict(zip(headers, values))
                    metric_name = row.get("Metric", "")
                    if metric_name:
                        metrics[metric_name] = row

        except Exception as e:
            print(f"⚠️  Warning: Could not parse performance CSV: {e}")

        return metrics

    def _load_security_results(self) -> Optional[Dict[str, Any]]:
        """Load security scan results."""
        security_dir = self.report_dir / "security"
        results_file = security_dir / "results.json"
        return self._load_json_file(results_file)

    def _calculate_pass_rate(self, passed: int, total: int) -> float:
        """Calculate pass rate percentage."""
        if total == 0:
            return 0.0
        return (passed / total) * 100.0

    def _get_status(self, passed: int, failed: int, errors: int, total: int) -> str:
        """Get status string based on test results."""
        if total == 0:
            return "NO_TESTS"
        if failed == 0 and errors == 0:
            return "✅ PASS"
        if failed > 0 or errors > 0:
            return "❌ FAIL"
        return "⚠️ PARTIAL"

    def _get_version_info(self) -> Dict[str, str]:
        """Get version information."""
        versions = {
            "python_version": platform.python_version(),
            "pytest_version": "unknown",
            "django_version": "unknown",
        }

        # Get pytest version
        try:
            result = subprocess.run(
                ["pytest", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                match = re.search(r"pytest\s+(\d+\.\d+\.\d+)", result.stdout)
                if match:
                    versions["pytest_version"] = match.group(1)
        except Exception:
            pass

        # Get Django version
        try:
            import django

            versions["django_version"] = django.get_version()
        except ImportError:
            pass

        return versions

    def _parse_use_cases(self) -> List[str]:
        """Parse use case IDs from USE_CASES.md."""
        use_cases = []
        if not USE_CASES_FILE.exists():
            return use_cases

        try:
            content = USE_CASES_FILE.read_text()
            # Match patterns like "### UC-AUTH-001:" or "**ID**: UC-AUTH-001"
            patterns = [
                r"###\s+UC-[\w-]+-\d+",
                r"\*\*ID\*\*:\s+UC-[\w-]+-\d+",
            ]
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    # Extract UC-XXX-XXX format
                    uc_match = re.search(r"UC-[\w-]+-\d+", match)
                    if uc_match:
                        uc_id = uc_match.group(0)
                        if uc_id not in use_cases:
                            use_cases.append(uc_id)
        except Exception as e:
            print(f"⚠️  Warning: Could not parse use cases: {e}")

        return sorted(use_cases)

    def _parse_journeys(self) -> List[str]:
        """Parse journey IDs from USER_JOURNEYS.md."""
        journeys = []
        if not USER_JOURNEYS_FILE.exists():
            return journeys

        try:
            content = USER_JOURNEYS_FILE.read_text()
            # Match patterns like "### JOURNEY-AUTH-001:" or "**Journey ID**: JOURNEY-AUTH-001"
            patterns = [
                r"###\s+JOURNEY-[\w-]+-\d+",
                r"\*\*Journey ID\*\*:\s+JOURNEY-[\w-]+-\d+",
            ]
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    # Extract JOURNEY-XXX-XXX format
                    journey_match = re.search(r"JOURNEY-[\w-]+-\d+", match)
                    if journey_match:
                        journey_id = journey_match.group(0)
                        if journey_id not in journeys:
                            journeys.append(journey_id)
        except Exception as e:
            print(f"⚠️  Warning: Could not parse journeys: {e}")

        return sorted(journeys)

    def _build_test_mappings(self):
        """Build mappings from test IDs to features, use cases, and journeys."""
        # Map tests to features by parsing test file paths
        for category, results in self.data["test_results"].items():
            if isinstance(results, dict):
                tests = results.get("tests", [])
                if not tests:
                    # Try alternative structures
                    if "summary" in results:
                        tests = results.get("test_cases", [])
                    elif "report" in results:
                        tests = results.get("report", {}).get("tests", [])

                for test in tests:
                    if isinstance(test, dict):
                        test_id = test.get("nodeid", test.get("test_id", ""))
                        if test_id:
                            # Map to feature
                            feature = self._extract_feature_from_test(test)
                            if feature != "Unknown":
                                self.test_to_feature_map[test_id] = feature

                            # Map to use case
                            use_case = self._extract_use_case_from_test(test)
                            if use_case != "Unknown":
                                self.test_to_use_case_map[test_id] = use_case

                            # Map to journey
                            journey = self._extract_journey_from_test(test)
                            if journey != "Unknown":
                                self.test_to_journey_map[test_id] = journey

    def _extract_journey_from_test(self, test: Dict[str, Any]) -> str:
        """Extract journey ID from test."""
        test_id = test.get("nodeid", test.get("test_id", ""))
        # Look for journey patterns like JOURNEY-AUTH-001
        match = re.search(r"JOURNEY-[\w-]+-\d+", test_id)
        if match:
            return match.group(0)
        return "Unknown"

    def collect_data(self):
        """Collect all test data from evidence files.
        Prefers Phase 12A evidence (phase_12a_1_summary.json, phase_12a_3_summary.json,
        JUnit XML per category) when present; otherwise uses summary.json and
        category/results.json per EVIDENCE_COLLECTION_PLAN.
        """
        print(f"📊 Collecting test data from {self.report_dir}...")

        # Parse use cases and journeys
        self.use_cases = self._parse_use_cases()
        self.journeys = self._parse_journeys()
        print(f"  Found {len(self.use_cases)} use cases and {len(self.journeys)} journeys")

        # Prefer Phase 12A evidence when present (gapfix1 7.4; testreview1 Phase 14)
        if self._load_phase_12a_evidence():
            print("  Loaded Phase 12A evidence (phase_12a_*_summary.json + JUnit XML)")
        else:
            # Load summary
            summary = self._load_summary()
            if summary:
                self.data["summary"] = summary
            else:
                self.data["summary"] = {}

            # Load test results by category
            self.data["test_results"] = {}
            for category in TEST_CATEGORIES:
                results = self._load_test_results(category)
                if results:
                    self.data["test_results"][category] = results

        # Build test mappings (may be no-op when only summary counts exist)
        self._build_test_mappings()

        # Load coverage data
        self.data["coverage"] = self._load_coverage_data()

        # Load performance metrics
        self.data["performance"] = self._load_performance_metrics()

        # Load security results
        self.data["security"] = self._load_security_results()

        # Get version info
        self.data["versions"] = self._get_version_info()

        print("✅ Data collection complete")

    def _calculate_category_stats(self, category: str) -> Dict[str, Any]:
        """Calculate statistics for a test category."""
        results = self.data["test_results"].get(category, {})
        if isinstance(results, dict) and "summary" in results:
            summary = results["summary"]
            total = summary.get("total", 0)
            passed = summary.get("passed", 0)
            failed = summary.get("failed", 0)
            skipped = summary.get("skipped", 0)
            errors = summary.get("errors", 0)
            duration = summary.get("duration", 0.0)
        else:
            # Try alternative structure
            total = results.get("total_tests", 0)
            passed = results.get("passed", 0)
            failed = results.get("failed", 0)
            skipped = results.get("skipped", 0)
            errors = results.get("errors", 0)
            duration = results.get("duration", 0.0)

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "duration": duration,
            "pass_rate": self._calculate_pass_rate(passed, total),
            "status": self._get_status(passed, failed, errors, total),
        }

    def _calculate_feature_stats(self, feature: str) -> Dict[str, Any]:
        """Calculate statistics for a feature."""
        stats = {
            "unit": 0,
            "integration": 0,
            "e2e": 0,
            "security": 0,
            "performance": 0,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "pass_rate": 0.0,
            "status": "⚠️ UNKNOWN",
        }

        # Count tests for this feature across all categories
        for category, results in self.data["test_results"].items():
            if isinstance(results, dict):
                tests = results.get("tests", [])
                if not tests:
                    tests = results.get("test_cases", [])
                if not tests and "report" in results:
                    tests = results.get("report", {}).get("tests", [])

                category_passed = 0
                category_failed = 0
                category_skipped = 0
                category_errors = 0
                category_total = 0

                for test in tests:
                    if isinstance(test, dict):
                        test_id = test.get("nodeid", test.get("test_id", ""))
                        mapped_feature = self.test_to_feature_map.get(test_id, "")
                        if mapped_feature == feature:
                            category_total += 1
                            status = test.get("outcome", test.get("status", ""))
                            if status in ["passed", "PASSED"]:
                                category_passed += 1
                            elif status in ["failed", "FAILED"]:
                                category_failed += 1
                            elif status in ["skipped", "SKIPPED"]:
                                category_skipped += 1
                            elif status in ["error", "ERROR"]:
                                category_errors += 1

                # Map category to feature stat key
                if category == "unit":
                    stats["unit"] = category_total
                elif category == "integration":
                    stats["integration"] = category_total
                elif category == "e2e":
                    stats["e2e"] = category_total
                elif category == "security":
                    stats["security"] = category_total
                elif category == "performance":
                    stats["performance"] = category_total

                stats["total"] += category_total
                stats["passed"] += category_passed
                stats["failed"] += category_failed
                stats["skipped"] += category_skipped
                stats["errors"] += category_errors

        # Calculate pass rate and status
        if stats["total"] > 0:
            stats["pass_rate"] = self._calculate_pass_rate(stats["passed"], stats["total"])
            stats["status"] = self._get_status(
                stats["passed"],
                stats["failed"],
                stats["errors"],
                stats["total"],
            )
        else:
            stats["status"] = "NO_TESTS"

        return stats

    def _calculate_use_case_stats(self, use_case_id: str) -> Dict[str, Any]:
        """Calculate statistics for a use case."""
        stats = {
            "unit": 0,
            "integration": 0,
            "e2e": 0,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "status": "⚠️ UNKNOWN",
        }

        # Count tests for this use case across all categories
        for category, results in self.data["test_results"].items():
            if isinstance(results, dict):
                tests = results.get("tests", [])
                if not tests:
                    tests = results.get("test_cases", [])
                if not tests and "report" in results:
                    tests = results.get("report", {}).get("tests", [])

                category_total = 0
                category_passed = 0
                category_failed = 0

                for test in tests:
                    if isinstance(test, dict):
                        test_id = test.get("nodeid", test.get("test_id", ""))
                        mapped_uc = self.test_to_use_case_map.get(test_id, "")
                        if mapped_uc == use_case_id:
                            category_total += 1
                            status = test.get("outcome", test.get("status", ""))
                            if status in ["passed", "PASSED"]:
                                category_passed += 1
                            elif status in ["failed", "FAILED", "error", "ERROR"]:
                                category_failed += 1

                # Map category to use case stat key
                if category == "unit":
                    stats["unit"] = category_total
                elif category == "integration":
                    stats["integration"] = category_total
                elif category == "e2e":
                    stats["e2e"] = category_total

                stats["total"] += category_total
                stats["passed"] += category_passed
                stats["failed"] += category_failed

        # Calculate status
        if stats["total"] > 0:
            if stats["failed"] == 0:
                stats["status"] = "✅ PASS"
            else:
                stats["status"] = "❌ FAIL"
        else:
            stats["status"] = "NO_TESTS"

        return stats

    def _calculate_journey_stats(self, journey_id: str) -> Dict[str, Any]:
        """Calculate statistics for a user journey."""
        stats = {
            "backend": 0,
            "frontend": 0,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "status": "⚠️ UNKNOWN",
        }

        # Count tests for this journey
        for category, results in self.data["test_results"].items():
            if isinstance(results, dict):
                tests = results.get("tests", [])
                if not tests:
                    tests = results.get("test_cases", [])
                if not tests and "report" in results:
                    tests = results.get("report", {}).get("tests", [])

                category_total = 0
                category_passed = 0
                category_failed = 0

                for test in tests:
                    if isinstance(test, dict):
                        test_id = test.get("nodeid", test.get("test_id", ""))
                        mapped_journey = self.test_to_journey_map.get(test_id, "")
                        if mapped_journey == journey_id:
                            category_total += 1
                            status = test.get("outcome", test.get("status", ""))
                            if status in ["passed", "PASSED"]:
                                category_passed += 1
                            elif status in ["failed", "FAILED", "error", "ERROR"]:
                                category_failed += 1

                # Map category to journey stat key
                if category == "e2e":
                    stats["backend"] = category_total
                elif category == "frontend-e2e":
                    stats["frontend"] = category_total

                stats["total"] += category_total
                stats["passed"] += category_passed
                stats["failed"] += category_failed

        # Calculate status
        if stats["total"] > 0:
            if stats["failed"] == 0:
                stats["status"] = "✅ PASS"
            else:
                stats["status"] = "❌ FAIL"
        else:
            stats["status"] = "NO_TESTS"

        return stats

    def _get_failed_tests(self) -> List[Dict[str, Any]]:
        """Extract failed tests from results."""
        failed_tests = []

        for category, results in self.data["test_results"].items():
            if isinstance(results, dict):
                # Try multiple JSON report formats
                tests = []

                # pytest-json-report format
                if "report" in results:
                    report = results["report"]
                    if "tests" in report:
                        tests = report["tests"]

                # Direct tests array
                if not tests and "tests" in results:
                    tests = results["tests"]

                # Alternative structure
                if not tests and "test_cases" in results:
                    tests = results["test_cases"]

                # Summary-based extraction (if individual tests not available)
                if not tests:
                    summary = results.get("summary", {})
                    failed_count = summary.get("failed", 0)
                    error_count = summary.get("error", 0)
                    if failed_count > 0 or error_count > 0:
                        # Create placeholder entries
                        for i in range(failed_count + error_count):
                            failed_tests.append(
                                {
                                    "id": f"{category}_failed_{i+1}",
                                    "name": f"Failed test {i+1} in {category}",
                                    "category": category,
                                    "feature": "Unknown",
                                    "use_case": "Unknown",
                                    "reason": "Test details not available in summary",
                                    "error": "Test details not available in summary",
                                    "fix_status": "PENDING",
                                    "priority": "MEDIUM",
                                }
                            )
                    continue

                for test in tests:
                    if isinstance(test, dict):
                        status = test.get("outcome", test.get("status", ""))
                        if status in ["failed", "FAILED", "error", "ERROR"]:
                            test_id = test.get("nodeid", test.get("test_id", ""))
                            test_name = test.get("name", test.get("test_name", test_id))

                            # Extract error message from various formats
                            error_msg = ""
                            if "call" in test:
                                call = test["call"]
                                error_msg = call.get("longrepr", call.get("crash", ""))
                            elif "setup" in test:
                                setup = test["setup"]
                                error_msg = setup.get("longrepr", "")
                            elif "teardown" in test:
                                teardown = test["teardown"]
                                error_msg = teardown.get("longrepr", "")

                            if not error_msg:
                                error_msg = test.get("error_message", test.get("message", ""))

                            # Truncate long error messages
                            if len(error_msg) > 500:
                                error_msg = error_msg[:500] + "..."

                            failed_tests.append(
                                {
                                    "id": test_id,
                                    "name": test_name,
                                    "category": category,
                                    "feature": self.test_to_feature_map.get(
                                        test_id, self._extract_feature_from_test(test)
                                    ),
                                    "use_case": self.test_to_use_case_map.get(
                                        test_id, self._extract_use_case_from_test(test)
                                    ),
                                    "reason": (
                                        error_msg[:200]
                                        if error_msg
                                        else "No error message available"
                                    ),
                                    "error": error_msg,
                                    "fix_status": "PENDING",
                                    "priority": self._determine_priority(test, category),
                                }
                            )

        return failed_tests

    def _determine_priority(self, test: Dict[str, Any], category: str) -> str:
        """Determine priority based on test characteristics."""
        test_id = test.get("nodeid", test.get("test_id", ""))

        # Critical if it's a security test or affects core features
        if category == "security":
            return "CRITICAL"
        if "auth" in test_id.lower() or "security" in test_id.lower():
            return "CRITICAL"

        # High if it's E2E or affects user journeys
        if category in ["e2e", "frontend-e2e"]:
            return "HIGH"
        if "journey" in test_id.lower():
            return "HIGH"

        # Medium for integration tests
        if category == "integration":
            return "MEDIUM"

        # Low for unit tests
        return "LOW"

    def _extract_feature_from_test(self, test: Dict[str, Any]) -> str:
        """Extract feature name from test."""
        test_id = test.get("nodeid", test.get("test_id", ""))
        # Simple heuristic: extract feature from test path
        # e.g., "hub/apps/auth/tests/test_*.py" -> "Auth"
        for feature in FEATURES:
            feature_lower = feature.lower().replace(" ", "_")
            if feature_lower in test_id.lower():
                return feature
        return "Unknown"

    def _extract_use_case_from_test(self, test: Dict[str, Any]) -> str:
        """Extract use case ID from test."""
        test_id = test.get("nodeid", test.get("test_id", ""))
        # Look for use case patterns like UC-AUTH-001
        match = re.search(r"UC-[\w-]+-\d+", test_id)
        if match:
            return match.group(0)
        return "Unknown"

    def _get_performance_metrics(self) -> List[Dict[str, Any]]:
        """Extract performance metrics."""
        metrics = []
        perf_data = self.data.get("performance", {})

        if isinstance(perf_data, dict):
            # Common performance metrics
            metric_names = [
                ("API Response Time (p50)", "p50", 50),
                ("API Response Time (p95)", "p95", 200),
                ("API Response Time (p99)", "p99", 500),
                ("Throughput (RPS)", "throughput", 30),
                ("Error Rate", "error_rate", 0.5),
            ]

            for name, key, target in metric_names:
                baseline = perf_data.get(f"{key}_baseline", 0)
                current = perf_data.get(key, perf_data.get(f"{key}_current", 0))
                change = current - baseline if baseline > 0 else 0
                change_pct = (change / baseline * 100) if baseline > 0 else 0
                status = "✅ PASS" if current <= target else "❌ FAIL"

                metrics.append(
                    {
                        "metric": name,
                        "baseline": f"{baseline}",
                        "current": f"{current}",
                        "change": f"{change:+.2f}",
                        "change_pct": f"{change_pct:+.2f}",
                        "status": status,
                        "target": f"≤{target}",
                    }
                )

        return metrics

    def _calculate_test_coverage(self) -> str:
        """Calculate test coverage percentage."""
        # Test coverage = (number of features/use cases/journeys with tests) / total
        features_with_tests = sum(
            1 for f in FEATURES if self._calculate_feature_stats(f)["total"] > 0
        )
        use_cases_with_tests = sum(
            1 for uc in self.use_cases if self._calculate_use_case_stats(uc)["total"] > 0
        )
        journeys_with_tests = sum(
            1 for j in self.journeys if self._calculate_journey_stats(j)["total"] > 0
        )

        total_entities = len(FEATURES) + len(self.use_cases) + len(self.journeys)
        entities_with_tests = features_with_tests + use_cases_with_tests + journeys_with_tests

        if total_entities > 0:
            coverage = (entities_with_tests / total_entities) * 100
            return f"{coverage:.1f}"
        return "0.0"

    def _calculate_code_coverage(self) -> str:
        """Calculate code coverage percentage from coverage.json."""
        coverage_data = self.data.get("coverage")
        if not coverage_data:
            return "0.0"

        # Try different coverage report formats
        if isinstance(coverage_data, dict):
            # Coverage.py format
            if "totals" in coverage_data:
                totals = coverage_data["totals"]
                if "percent_covered" in totals:
                    return f"{totals['percent_covered']:.1f}"
                elif "percent_covered_display" in totals:
                    return totals["percent_covered_display"].replace("%", "")

            # Alternative format
            if "coverage_percent" in coverage_data:
                return f"{coverage_data['coverage_percent']:.1f}"

        return "0.0"

    def _get_security_vulnerabilities(self) -> List[Dict[str, Any]]:
        """Extract security vulnerabilities."""
        vulnerabilities = []
        security_data = self.data.get("security", {})

        if isinstance(security_data, dict):
            vulns = security_data.get("vulnerabilities", security_data.get("results", []))
            if isinstance(vulns, list):
                for vuln in vulns:
                    if isinstance(vuln, dict):
                        vulnerabilities.append(
                            {
                                "id": vuln.get("id", ""),
                                "name": vuln.get("name", vuln.get("title", "")),
                                "severity": vuln.get("severity", "UNKNOWN"),
                                "category": vuln.get("category", ""),
                                "status": vuln.get("status", "OPEN"),
                                "fix_status": vuln.get("fix_status", "PENDING"),
                                "cve": vuln.get("cve", ""),
                                "cvss": vuln.get("cvss_score", vuln.get("cvss", "")),
                            }
                        )

        return vulnerabilities

    def _generate_recommendations(self) -> Dict[str, List[str]]:
        """Generate recommendations based on test results."""
        recommendations: Dict[str, List[str]] = {
            "coverage": [],
            "performance": [],
            "security": [],
            "quality": [],
            "infrastructure": [],
        }

        # Coverage recommendations
        total_tests = sum(
            self._calculate_category_stats(cat).get("total", 0) for cat in TEST_CATEGORIES
        )
        if total_tests < 1000:
            recommendations["coverage"].append(
                "Increase test coverage to meet minimum threshold " "of 1000 tests"
            )

        # Performance recommendations
        perf_metrics = self._get_performance_metrics()
        failed_perf = [m for m in perf_metrics if "FAIL" in m.get("status", "")]
        if failed_perf:
            recommendations["performance"].append(
                f"Address {len(failed_perf)} performance metrics " "that are not meeting targets"
            )

        # Security recommendations
        vulnerabilities = self._get_security_vulnerabilities()
        critical_vulns = [v for v in vulnerabilities if v.get("severity") == "CRITICAL"]
        if critical_vulns:
            recommendations["security"].append(
                f"Address {len(critical_vulns)} critical security " "vulnerabilities immediately"
            )

        return recommendations

    def generate_report(self) -> str:
        """Generate the test summary report."""
        print("📝 Generating test summary report...")

        # Calculate overall statistics
        category_stats = {}
        for category in TEST_CATEGORIES:
            category_stats[category] = self._calculate_category_stats(category)

        # Calculate totals
        total_all = sum(stats.get("total", 0) for stats in category_stats.values())
        total_passed_all = sum(stats.get("passed", 0) for stats in category_stats.values())
        total_failed_all = sum(stats.get("failed", 0) for stats in category_stats.values())
        total_skipped_all = sum(stats.get("skipped", 0) for stats in category_stats.values())
        total_errors_all = sum(stats.get("errors", 0) for stats in category_stats.values())
        total_duration_all = sum(stats.get("duration", 0) for stats in category_stats.values())
        overall_pass_rate = self._calculate_pass_rate(total_passed_all, total_all)
        overall_status = self._get_status(
            total_passed_all, total_failed_all, total_errors_all, total_all
        )

        # Get failed tests
        failed_tests = self._get_failed_tests()

        # Get performance metrics
        performance_metrics = self._get_performance_metrics()

        # Get security vulnerabilities
        security_vulnerabilities = self._get_security_vulnerabilities()

        # Generate recommendations
        recommendations = self._generate_recommendations()

        # Prepare replacement dictionary
        replacements = {
            # Executive Summary
            "{date}": self.date,
            "{version}": "1.0.0",
            "{suite_name}": "Comprehensive Test Suite",
            "{environment}": "Development",
            "{generated_by}": "Test Summary Report Generator",
            "{overall_status}": overall_status,
            "{total_tests}": str(total_all),
            "{passed_tests}": str(total_passed_all),
            "{passed_percentage}": f"{self._calculate_pass_rate(total_passed_all, total_all):.1f}",
            "{failed_tests}": str(total_failed_all),
            "{failed_percentage}": (
                f"{(total_failed_all / total_all * 100) if total_all > 0 else 0:.1f}"
            ),
            "{skipped_tests}": str(total_skipped_all),
            "{skipped_percentage}": (
                f"{(total_skipped_all / total_all * 100) if total_all > 0 else 0:.1f}"
            ),
            "{error_tests}": str(total_errors_all),
            "{error_percentage}": (
                f"{(total_errors_all / total_all * 100) if total_all > 0 else 0:.1f}"
            ),
            "{total_duration}": f"{total_duration_all:.2f}s",
            "{success_rate}": f"{overall_pass_rate:.1f}",
            "{test_coverage}": self._calculate_test_coverage(),
            "{code_coverage}": self._calculate_code_coverage(),
            "{performance_status}": (
                "✅ PASS"
                if not any("FAIL" in m.get("status", "") for m in performance_metrics)
                else "❌ FAIL"
            ),
            "{security_status}": ("✅ PASS" if not security_vulnerabilities else "⚠️ ISSUES"),
            "{critical_issues_count}": str(
                len([v for v in security_vulnerabilities if v.get("severity") == "CRITICAL"])
            ),
            # Test Execution Summary
            "{execution_date}": self.date,
            "{execution_time}": datetime.now().strftime("%H:%M:%S"),
            "{suite_version}": "1.0.0",
            "{pytest_version}": (self.data["versions"].get("pytest_version", "unknown")),
            "{python_version}": (self.data["versions"].get("python_version", "unknown")),
            "{django_version}": (self.data["versions"].get("django_version", "unknown")),
            "{total_test_files}": "0",  # Would need to count from results
            "{total_test_cases}": str(total_all),
            "{total_assertions}": "0",  # Would need to count from results
            "{execution_duration}": f"{total_duration_all:.2f}s",
            "{average_test_duration}": (
                f"{(total_duration_all / total_all) if total_all > 0 else 0:.3f}s"
            ),
            # Category stats (using helper function)
        }

        # Add category-specific replacements
        for category in TEST_CATEGORIES:
            stats = category_stats.get(category, {})
            prefix = category.replace("-", "_")
            replacements.update(
                {
                    f"{{{prefix}_total}}": str(stats.get("total", 0)),
                    f"{{{prefix}_passed}}": str(stats.get("passed", 0)),
                    f"{{{prefix}_failed}}": str(stats.get("failed", 0)),
                    f"{{{prefix}_skipped}}": str(stats.get("skipped", 0)),
                    f"{{{prefix}_errors}}": str(stats.get("errors", 0)),
                    f"{{{prefix}_duration}}": f"{stats.get('duration', 0):.2f}s",
                    f"{{{prefix}_status}}": stats.get("status", "UNKNOWN"),
                    f"{{{prefix}_pass_rate}}": f"{stats.get('pass_rate', 0):.1f}",
                }
            )

        # Add totals
        replacements.update(
            {
                "{total_all}": str(total_all),
                "{total_passed_all}": str(total_passed_all),
                "{total_failed_all}": str(total_failed_all),
                "{total_skipped_all}": str(total_skipped_all),
                "{total_errors_all}": str(total_errors_all),
                "{total_duration_all}": f"{total_duration_all:.2f}s",
                "{overall_status_all}": overall_status,
                "{overall_pass_rate}": f"{overall_pass_rate:.1f}",
            }
        )

        # Evidence links (gapfix1 7.4.1: links to category artifact dirs)
        evidence_lines = []
        for category in TEST_CATEGORIES:
            rel_path = f"test_reports_comprehensive/{self.date}/{category}/"
            evidence_lines.append(f"- **{category}**: `{rel_path}`")
        replacements["{evidence_links}"] = "\n".join(evidence_lines) if evidence_lines else "(no categories)"

        # Feature stats (actual calculation)
        for feature in FEATURES:
            feature_key = feature.lower().replace(" ", "_")
            stats = self._calculate_feature_stats(feature)
            replacements.update(
                {
                    f"{{{feature_key}_unit}}": str(stats["unit"]),
                    f"{{{feature_key}_integration}}": str(stats["integration"]),
                    f"{{{feature_key}_e2e}}": str(stats["e2e"]),
                    f"{{{feature_key}_security}}": str(stats["security"]),
                    f"{{{feature_key}_performance}}": str(stats["performance"]),
                    f"{{{feature_key}_total}}": str(stats["total"]),
                    f"{{{feature_key}_pass_rate}}": f"{stats['pass_rate']:.1f}",
                    f"{{{feature_key}_status}}": stats["status"],
                }
            )

        # Use case stats (actual calculation)
        for use_case_id in self.use_cases:
            uc_key = use_case_id.lower().replace("-", "_")
            stats = self._calculate_use_case_stats(use_case_id)
            replacements.update(
                {
                    f"{{{uc_key}_unit}}": str(stats["unit"]),
                    f"{{{uc_key}_integration}}": str(stats["integration"]),
                    f"{{{uc_key}_e2e}}": str(stats["e2e"]),
                    f"{{{uc_key}_status}}": stats["status"],
                }
            )

        # Journey stats (actual calculation)
        for journey_id in self.journeys:
            journey_key = journey_id.lower().replace("-", "_")
            stats = self._calculate_journey_stats(journey_id)
            replacements.update(
                {
                    f"{{{journey_key}_backend}}": str(stats["backend"]),
                    f"{{{journey_key}_frontend}}": str(stats["frontend"]),
                    f"{{{journey_key}_status}}": stats["status"],
                }
            )

        # Failed tests table
        failed_tests_table = ""
        for test in failed_tests[:50]:  # Limit to 50 for readability
            test_id = test.get("id", "")
            test_name = test.get("name", "")
            category = test.get("category", "")
            feature = test.get("feature", "")
            use_case = test.get("use_case", "")
            reason = test.get("reason", "")[:100]
            error = test.get("error", "")[:100]
            fix_status = test.get("fix_status", "")
            priority = test.get("priority", "")
            failed_tests_table += (
                f"| {test_id} | {test_name} | {category} | {feature} | "
                f"{use_case} | {reason} | {error} | {fix_status} | "
                f"{priority} |\n"
            )

        replacements["{failed_test_id_1}"] = failed_tests[0].get("id", "") if failed_tests else ""
        replacements["{failed_test_name_1}"] = (
            failed_tests[0].get("name", "") if failed_tests else ""
        )
        # ... (would need to add all failed test placeholders)

        replacements["{total_failed_tests}"] = str(len(failed_tests))
        replacements["{critical_failures}"] = str(
            len([t for t in failed_tests if t.get("priority") == "CRITICAL"])
        )
        replacements["{high_priority_failures}"] = str(
            len([t for t in failed_tests if t.get("priority") == "HIGH"])
        )

        # Performance metrics table
        perf_table = ""
        for metric in performance_metrics:
            metric_name = metric.get("metric", "")
            baseline = metric.get("baseline", "")
            current = metric.get("current", "")
            change = metric.get("change", "")
            change_pct = metric.get("change_pct", "")
            status = metric.get("status", "")
            target = metric.get("target", "")
            perf_table += (
                f"| {metric_name} | {baseline} | {current} | {change} | "
                f"{change_pct}% | {status} | {target} |\n"
            )

        # Security vulnerabilities table
        sec_table = ""
        for vuln in security_vulnerabilities[:50]:  # Limit to 50
            vuln_id = vuln.get("id", "")
            vuln_name = vuln.get("name", "")
            severity = vuln.get("severity", "")
            category = vuln.get("category", "")
            status = vuln.get("status", "")
            fix_status = vuln.get("fix_status", "")
            cve = vuln.get("cve", "")
            cvss = vuln.get("cvss", "")
            sec_table += (
                f"| {vuln_id} | {vuln_name} | {severity} | {category} | "
                f"{status} | {fix_status} | {cve} | {cvss} |\n"
            )

        replacements["{total_vulnerabilities}"] = str(len(security_vulnerabilities))
        replacements["{critical_vulnerabilities}"] = str(
            len([v for v in security_vulnerabilities if v.get("severity") == "CRITICAL"])
        )

        # Recommendations
        replacements["{recommendations_coverage}"] = "\n".join(
            f"- {r}" for r in recommendations["coverage"]
        )
        replacements["{recommendations_performance}"] = "\n".join(
            f"- {r}" for r in recommendations["performance"]
        )
        replacements["{recommendations_security}"] = "\n".join(
            f"- {r}" for r in recommendations["security"]
        )
        replacements["{recommendations_quality}"] = "\n".join(
            f"- {r}" for r in recommendations["quality"]
        )
        replacements["{recommendations_infrastructure}"] = "\n".join(
            f"- {r}" for r in recommendations["infrastructure"]
        )

        # Evidence links
        replacements["{report_generation_date}"] = datetime.now().isoformat()

        # Replace all placeholders in template
        report = self.template
        for placeholder, value in replacements.items():
            report = report.replace(placeholder, str(value))

        # Generate use case and journey tables dynamically and replace placeholders
        report = self._replace_use_case_tables(report)
        report = self._replace_journey_tables(report)

        # Replace remaining placeholders with "N/A" or "0"
        remaining_placeholders = re.findall(r"\{[^}]+\}", report)
        for placeholder in remaining_placeholders:
            if placeholder not in ["{date}", "{version}"]:
                # Keep some placeholders
                if "status" in placeholder.lower():
                    report = report.replace(placeholder, "⚠️ UNKNOWN")
                elif "rate" in placeholder.lower() or "percentage" in placeholder.lower():
                    report = report.replace(placeholder, "0.0")
                elif any(x in placeholder.lower() for x in ["total", "count", "number"]):
                    report = report.replace(placeholder, "0")
                else:
                    report = report.replace(placeholder, "N/A")

        return report

    def _replace_use_case_tables(self, report: str) -> str:
        """Replace use case table placeholders with actual data."""
        # Find the use case section
        use_case_section_pattern = r"## Test Results by Use Case.*?(?=##|$)"
        match = re.search(use_case_section_pattern, report, re.DOTALL)
        if not match:
            return report

        # Generate use case tables by category
        use_case_tables = []

        # Group use cases by prefix (UC-AUTH, UC-AM, etc.)
        use_case_groups: Dict[str, List[str]] = {}
        for uc_id in self.use_cases:
            prefix = uc_id.split("-")[1] if "-" in uc_id else "OTHER"
            if prefix not in use_case_groups:
                use_case_groups[prefix] = []
            use_case_groups[prefix].append(uc_id)

        # Generate table for each group
        for prefix, use_cases in sorted(use_case_groups.items()):
            table_lines = [f"### {prefix} Use Cases", ""]
            table_lines.append(
                "| Use Case ID | Use Case Name | Unit Tests | Integration Tests | E2E Tests | Status |"
            )
            table_lines.append(
                "|-------------|---------------|-----------|------------------|----------|--------|"
            )

            for uc_id in sorted(use_cases):
                stats = self._calculate_use_case_stats(uc_id)
                # Extract use case name (simplified - would need to parse USE_CASES.md)
                uc_name = uc_id.replace("UC-", "").replace("-", " ")
                table_lines.append(
                    f"| {uc_id} | {uc_name} | {stats['unit']} | "
                    f"{stats['integration']} | {stats['e2e']} | "
                    f"{stats['status']} |"
                )

            use_case_tables.append("\n".join(table_lines))

        # Replace the section
        new_section = "## Test Results by Use Case\n\n" + "\n\n".join(use_case_tables)
        report = re.sub(
            use_case_section_pattern,
            new_section + "\n\n---\n\n",
            report,
            flags=re.DOTALL,
        )

        return report

    def _replace_journey_tables(self, report: str) -> str:
        """Replace journey table placeholders with actual data."""
        # Find the journey section
        journey_section_pattern = r"## Test Results by User Journey.*?(?=##|$)"
        match = re.search(journey_section_pattern, report, re.DOTALL)
        if not match:
            return report

        # Generate journey tables by persona/category
        journey_tables = []

        # Group journeys by prefix (JOURNEY-AUTH, JOURNEY-DPO, etc.)
        journey_groups: Dict[str, List[str]] = {}
        for journey_id in self.journeys:
            parts = journey_id.split("-")
            if len(parts) >= 2:
                prefix = parts[1]  # AUTH, DPO, etc.
            else:
                prefix = "OTHER"
            if prefix not in journey_groups:
                journey_groups[prefix] = []
            journey_groups[prefix].append(journey_id)

        # Generate table for each group
        for prefix, journeys in sorted(journey_groups.items()):
            # Map prefix to persona name
            persona_map = {
                "AUTH": "Visitor / Authentication",
                "DPO": "Data Product Owner",
                "DE": "Data Engineer",
                "CPO": "Compliance Officer",
                "DC": "Data Consumer",
                "TA": "Tenant Admin",
                "PA": "Platform Admin",
                "DEV": "External Developer",
                "AUD": "Auditor",
                "DS": "Data Scientist",
                "DA": "Data Analyst",
                "CM": "Community Manager",
                "DMO": "Data Mesh Domain Owner",
            }
            persona_name = persona_map.get(prefix, prefix)

            table_lines = [f"### {persona_name} Journeys", ""]
            table_lines.append(
                "| Journey ID | Journey Name | Backend E2E | Frontend E2E | Status |"
            )
            table_lines.append("|------------|--------------|------------|-------------|--------|")

            for journey_id in sorted(journeys):
                stats = self._calculate_journey_stats(journey_id)
                # Extract journey name (simplified - would need to parse USER_JOURNEYS.md)
                journey_name = journey_id.replace("JOURNEY-", "").replace("-", " ")
                table_lines.append(
                    f"| {journey_id} | {journey_name} | {stats['backend']} | "
                    f"{stats['frontend']} | {stats['status']} |"
                )

            journey_tables.append("\n".join(table_lines))

        # Replace the section
        new_section = "## Test Results by User Journey\n\n" + "\n\n".join(journey_tables)
        report = re.sub(
            journey_section_pattern,
            new_section + "\n\n---\n\n",
            report,
            flags=re.DOTALL,
        )

        return report

    def save_report(self, report: str):
        """Save the generated report to file."""
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.output_file.write_text(report)
        print(f"✅ Report saved to: {self.output_file}")

    def run(self):
        """Run the complete report generation process."""
        print("=" * 80)
        print("Test Summary Report Generator")
        print("=" * 80)
        print(f"Date: {self.date}")
        print(f"Report Directory: {self.report_dir}")
        print(f"Output File: {self.output_file}")
        print()

        try:
            self.collect_data()
            report = self.generate_report()
            self.save_report(report)
            print()
            print("✅ Report generation complete!")
        except Exception as e:
            print(f"❌ Error generating report: {e}")
            import traceback

            traceback.print_exc()
            sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description=("Generate comprehensive test summary report " "from collected evidence")
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Date string (YYYY-MM-DD) or 'latest' for latest available date",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: auto-generated)",
    )

    args = parser.parse_args()

    date = args.date if args.date and args.date != "latest" else None
    output_file = Path(args.output) if args.output else None

    generator = TestSummaryReportGenerator(date=date, output_file=output_file)
    generator.run()


if __name__ == "__main__":
    main()
