#!/usr/bin/env python3
"""
Compliance Endpoint Verification Script

This script verifies that all consumers have been updated to use the
standardized compliance endpoint pattern: /api/v1/compliance/runs/

It searches for old patterns and verifies all consumers are using the new pattern.
"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EndpointReference:
    """Represents a reference to an endpoint"""

    file_path: str
    line_number: int
    line_content: str
    pattern_type: str  # 'old', 'new', or 'ambiguous'
    endpoint_pattern: str
    context: str = ""


@dataclass
class ConsumerVerification:
    """Verification result for a consumer"""

    consumer_name: str
    consumer_type: str  # 'cli', 'sdk', 'service_client', 'workflow', 'test', 'other'
    file_path: str
    status: str  # 'verified', 'needs_update', 'not_found'
    old_patterns_found: list[str]
    new_patterns_found: list[str]
    references: list[EndpointReference]


class ComplianceEndpointVerifier:
    """Verifies compliance endpoint usage across the codebase"""

    # Old patterns to search for (various forms)
    OLD_PATTERNS = [
        r"compliance/compliance-runs",
        r"compliance-runs",
        r"compliance/compliance_runs",
        r"compliance_runs",
        r"/api/v1/compliance/compliance-runs",
        r"/api/v1/compliance/compliance_runs",
    ]

    # New standardized pattern
    NEW_PATTERN = r"compliance/runs"

    # Consumer locations to check
    CONSUMER_LOCATIONS = {
        "cli": "cli/datahub_cli/commands/",
        "sdk_js": "sdk/js/src/",
        "service_clients": "hub/apps/api/utils/service_clients.py",
        "workflows": "hub/apps/orchestration/workflows/",
        "tests": [
            "hub/apps/compliance/tests/",
            "cli/tests/",
            "sdk/js/src/__tests__/",
        ],
    }

    # Files to exclude from search
    EXCLUDE_PATTERNS = [
        r"\.pyc$",
        r"__pycache__",
        r"\.git",
        r"node_modules",
        r"\.venv",
        r"venv/",
        r"dist/",
        r"build/",
        r"\.pytest_cache",
        r"\.mypy_cache",
        r"docs/",
        r"\.md$",  # Exclude markdown files (documentation)
        r"scripts/migrations/",  # Migration scripts (historical references)
        r"scripts/estimate-all-api-efforts\.py",  # Estimation script (historical references)
        r"scripts/update-backlog-with-effort-estimates\.py",  # Estimation script
        r"scripts/document-gap-details\.py",  # Documentation script
        r"scripts/verify-compliance-endpoints\.py",  # This verification script itself
        r"verification-report.*\.json",  # Generated report
    ]

    # Patterns that indicate a negative assertion (checking for absence)
    NEGATIVE_ASSERTION_PATTERNS = [
        r"not\.toContain",
        r"not\.toMatch",
        r"not\.toHave",
        r"assertNotIn",
        r"assert.*not.*contain",
        r"does.*not.*contain",
        r"should.*not.*contain",
    ]

    # Patterns that indicate metrics (not API endpoints)
    METRICS_PATTERNS = [
        r"_total",
        r"_count",
        r"_gauge",
        r"_histogram",
        r"\.labels\(",
        r"\.inc\(",
        r"\.set\(",
        r"prometheus",
        r"metrics",
    ]

    # Patterns that indicate test function names or variable names (not API endpoints)
    TEST_FUNCTION_PATTERNS = [
        r"def test_",
        r"def _\w*compliance",
        r"class Test",
        r"it\(.*compliance",
        r"describe\(.*compliance",
        r"self\._",
        r"self\.assertIn\(.*compliance",
        r"report\.report_data",
        r"report_data\[",
    ]

    def __init__(self, root_dir: str = None):
        """Initialize verifier"""
        if root_dir is None:
            root_dir = Path(__file__).parent.parent
        self.root_dir = Path(root_dir)
        self.references: list[EndpointReference] = []
        self.consumer_verifications: list[ConsumerVerification] = []

    def should_exclude_file(self, file_path: Path) -> bool:
        """Check if file should be excluded from search"""
        file_str = str(file_path)
        for pattern in self.EXCLUDE_PATTERNS:
            if re.search(pattern, file_str):
                return True
        return False

    def is_negative_assertion(self, line: str) -> bool:
        """Check if line is a negative assertion (checking for absence)"""
        for pattern in self.NEGATIVE_ASSERTION_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        return False

    def is_metrics_reference(self, line: str) -> bool:
        """Check if line is a metrics reference (not an API endpoint)"""
        for pattern in self.METRICS_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        return False

    def is_test_function_name(self, line: str) -> bool:
        """Check if line is a test function name (not an API endpoint)"""
        for pattern in self.TEST_FUNCTION_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        return False

    def search_file(self, file_path: Path) -> list[EndpointReference]:
        """Search a file for endpoint references"""
        references = []

        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                for line_num, line in enumerate(lines, 1):
                    # Skip negative assertions (they're checking that old patterns DON'T exist)
                    if self.is_negative_assertion(line):
                        continue

                    # Check for old patterns (only flag actual API endpoint URLs)
                    for pattern in self.OLD_PATTERNS:
                        if re.search(pattern, line, re.IGNORECASE):
                            # Only flag if it's an actual API endpoint URL
                            if not re.search(
                                r"/api/v1/|http://|https://|post\(|get\(|put\(|delete\(|\.post\(|\.get\(|\.put\(|\.delete\(",
                                line,
                                re.IGNORECASE,
                            ):
                                continue
                            # Skip if this is clearly a metrics reference (not an API endpoint)
                            if self.is_metrics_reference(line) and not re.search(
                                r"/api/v1/", line, re.IGNORECASE
                            ):
                                continue
                            # Skip if this is a test function name (descriptive, not an endpoint)
                            if self.is_test_function_name(line):
                                continue
                            # Skip database table names, related names, variable names
                            if re.search(
                                r"db_table\s*=|related_name\s*=|def\s+\w*compliance|compliance_runs\s*=|compliance_runs\.get\(|compliance_runs\s*\[|compliance_runs\s*\{|isinstance\(compliance_runs",
                                line,
                                re.IGNORECASE,
                            ):
                                continue
                            # Skip test assertions that check old URLs don't resolve (they're testing the right thing)
                            if re.search(
                                r"resolve\(.*compliance.*compliance-runs|test.*old.*endpoint|test.*old.*url|test.*old.*pattern|endpoint.*not.*accessible|does.*not.*resolve",
                                line,
                                re.IGNORECASE,
                            ):
                                continue
                            # Skip test cases that verify old endpoints return 404 (they're intentionally using old URLs)
                            if re.search(
                                r"client\.get\(.*compliance.*compliance-runs|client\.post\(.*compliance.*compliance-runs",
                                line,
                                re.IGNORECASE,
                            ):
                                # Check if it's in a test that expects 404
                                context_lines = self._get_context(
                                    file_path, line_num, context_lines=5
                                )
                                if re.search(
                                    r"404|NOT_FOUND|does.*not.*resolve|not.*accessible",
                                    context_lines,
                                    re.IGNORECASE,
                                ):
                                    continue
                            ref = EndpointReference(
                                file_path=str(file_path.relative_to(self.root_dir)),
                                line_number=line_num,
                                line_content=line.strip(),
                                pattern_type="old",
                                endpoint_pattern=pattern,
                                context=self._get_context(file_path, line_num),
                            )
                            references.append(ref)

                    # Check for new pattern (don't filter metrics for new pattern - it's valid)
                    if re.search(self.NEW_PATTERN, line, re.IGNORECASE):
                        ref = EndpointReference(
                            file_path=str(file_path.relative_to(self.root_dir)),
                            line_number=line_num,
                            line_content=line.strip(),
                            pattern_type="new",
                            endpoint_pattern=self.NEW_PATTERN,
                            context=self._get_context(file_path, line_num),
                        )
                        references.append(ref)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

        return references

    def _get_context(self, file_path: Path, line_num: int, context_lines: int = 2) -> str:
        """Get context around a line"""
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                start = max(0, line_num - context_lines - 1)
                end = min(len(lines), line_num + context_lines)
                context = "".join(lines[start:end])
                return context
        except:
            return ""

    def search_codebase(self) -> list[EndpointReference]:
        """Search entire codebase for endpoint references"""
        print("Searching codebase for compliance endpoint references...")
        references = []

        # Search Python files
        for py_file in self.root_dir.rglob("*.py"):
            if not self.should_exclude_file(py_file):
                refs = self.search_file(py_file)
                references.extend(refs)

        # Search TypeScript/JavaScript files
        for ts_file in self.root_dir.rglob("*.ts"):
            if not self.should_exclude_file(ts_file):
                refs = self.search_file(ts_file)
                references.extend(refs)

        for js_file in self.root_dir.rglob("*.js"):
            if not self.should_exclude_file(js_file):
                refs = self.search_file(js_file)
                references.extend(refs)

        self.references = references
        return references

    def verify_consumer(
        self, consumer_name: str, consumer_type: str, file_path: str
    ) -> ConsumerVerification:
        """Verify a specific consumer"""
        full_path = self.root_dir / file_path

        if not full_path.exists():
            return ConsumerVerification(
                consumer_name=consumer_name,
                consumer_type=consumer_type,
                file_path=file_path,
                status="not_found",
                old_patterns_found=[],
                new_patterns_found=[],
                references=[],
            )

        # Find references in this file
        file_refs = [ref for ref in self.references if ref.file_path == file_path]

        old_patterns = [ref.endpoint_pattern for ref in file_refs if ref.pattern_type == "old"]
        new_patterns = [ref.endpoint_pattern for ref in file_refs if ref.pattern_type == "new"]

        # Determine status
        if old_patterns:
            status = "needs_update"
        elif new_patterns:
            status = "verified"
        else:
            status = "not_found"

        return ConsumerVerification(
            consumer_name=consumer_name,
            consumer_type=consumer_type,
            file_path=file_path,
            status=status,
            old_patterns_found=list(set(old_patterns)),
            new_patterns_found=list(set(new_patterns)),
            references=file_refs,
        )

    def verify_all_consumers(self) -> list[ConsumerVerification]:
        """Verify all known consumers"""
        verifications = []

        # Verify CLI
        cli_file = "cli/datahub_cli/commands/compliance.py"
        verifications.append(self.verify_consumer("CLI Compliance Commands", "cli", cli_file))

        # Verify JavaScript SDK
        sdk_files = [
            "sdk/js/src/compliance.ts",
            "sdk/js/src/index.ts",
            "sdk/js/src/client.ts",
        ]
        for sdk_file in sdk_files:
            verifications.append(
                self.verify_consumer(f"JavaScript SDK - {Path(sdk_file).name}", "sdk", sdk_file)
            )

        # Verify Service Clients
        service_client_file = "hub/apps/api/utils/service_clients.py"
        verifications.append(
            self.verify_consumer("Service Clients", "service_client", service_client_file)
        )

        # Verify Workflows (check directory)
        workflow_dir = self.root_dir / "hub/apps/orchestration/workflows"
        if workflow_dir.exists():
            for workflow_file in workflow_dir.rglob("*.py"):
                rel_path = str(workflow_file.relative_to(self.root_dir))
                if not self.should_exclude_file(workflow_file):
                    verifications.append(
                        self.verify_consumer(
                            f"Workflow - {workflow_file.name}", "workflow", rel_path
                        )
                    )

        # Verify Tests
        test_dirs = [
            "hub/apps/compliance/tests/",
            "cli/tests/",
            "sdk/js/src/__tests__/",
        ]
        for test_dir in test_dirs:
            test_path = self.root_dir / test_dir
            if test_path.exists():
                for test_file in test_path.rglob("*.py"):
                    rel_path = str(test_file.relative_to(self.root_dir))
                    if not self.should_exclude_file(test_file):
                        verifications.append(
                            self.verify_consumer(f"Test - {test_file.name}", "test", rel_path)
                        )
                for test_file in test_path.rglob("*.ts"):
                    rel_path = str(test_file.relative_to(self.root_dir))
                    if not self.should_exclude_file(test_file):
                        verifications.append(
                            self.verify_consumer(f"Test - {test_file.name}", "test", rel_path)
                        )

        self.consumer_verifications = verifications
        return verifications

    def generate_report(self) -> dict:
        """Generate verification report"""
        # Count statistics
        total_references = len(self.references)
        old_pattern_count = len([r for r in self.references if r.pattern_type == "old"])
        new_pattern_count = len([r for r in self.references if r.pattern_type == "new"])

        # Consumer statistics
        consumers_verified = len([v for v in self.consumer_verifications if v.status == "verified"])
        consumers_needs_update = len(
            [v for v in self.consumer_verifications if v.status == "needs_update"]
        )
        consumers_not_found = len(
            [v for v in self.consumer_verifications if v.status == "not_found"]
        )

        # Group by consumer type
        by_type = defaultdict(list)
        for v in self.consumer_verifications:
            by_type[v.consumer_type].append(v)

        report = {
            "summary": {
                "total_references": total_references,
                "old_patterns_found": old_pattern_count,
                "new_patterns_found": new_pattern_count,
                "consumers_verified": consumers_verified,
                "consumers_needs_update": consumers_needs_update,
                "consumers_not_found": consumers_not_found,
                "verification_status": "PASS" if old_pattern_count == 0 else "FAIL",
            },
            "old_patterns": [
                {
                    "file": ref.file_path,
                    "line": ref.line_number,
                    "pattern": ref.endpoint_pattern,
                    "content": ref.line_content,
                }
                for ref in self.references
                if ref.pattern_type == "old"
            ],
            "consumers": {
                consumer_type: [
                    {
                        "name": v.consumer_name,
                        "file": v.file_path,
                        "status": v.status,
                        "old_patterns": v.old_patterns_found,
                        "new_patterns": v.new_patterns_found,
                    }
                    for v in consumers
                ]
                for consumer_type, consumers in by_type.items()
            },
            "references_by_file": {},
        }

        # Group references by file
        by_file = defaultdict(list)
        for ref in self.references:
            by_file[ref.file_path].append(
                {
                    "line": ref.line_number,
                    "type": ref.pattern_type,
                    "pattern": ref.endpoint_pattern,
                    "content": ref.line_content,
                }
            )

        report["references_by_file"] = dict(by_file)

        return report

    def print_report(self, report: dict):
        """Print human-readable report"""
        print("\n" + "=" * 80)
        print("COMPLIANCE ENDPOINT VERIFICATION REPORT")
        print("=" * 80)

        summary = report["summary"]
        print("\nSUMMARY:")
        print(f"  Total References Found: {summary['total_references']}")
        print(f"  Old Patterns Found: {summary['old_patterns_found']}")
        print(f"  New Patterns Found: {summary['new_patterns_found']}")
        print(f"  Consumers Verified: {summary['consumers_verified']}")
        print(f"  Consumers Needing Update: {summary['consumers_needs_update']}")
        print(f"  Verification Status: {summary['verification_status']}")

        if summary["old_patterns_found"] > 0:
            print(f"\n⚠️  WARNING: {summary['old_patterns_found']} old pattern(s) found!")
            print("\nOLD PATTERNS FOUND:")
            for pattern in report["old_patterns"]:
                print(f"  - {pattern['file']}:{pattern['line']}")
                print(f"    Pattern: {pattern['pattern']}")
                print(f"    Content: {pattern['content'][:100]}")
        else:
            print("\n✅ No old patterns found - all consumers using standardized endpoints!")

        print("\nCONSUMER VERIFICATION:")
        for consumer_type, consumers in report["consumers"].items():
            print(f"\n  {consumer_type.upper()}:")
            for consumer in consumers:
                status_icon = (
                    "✅"
                    if consumer["status"] == "verified"
                    else "❌"
                    if consumer["status"] == "needs_update"
                    else "⚠️"
                )
                print(f"    {status_icon} {consumer['name']}")
                print(f"       File: {consumer['file']}")
                print(f"       Status: {consumer['status']}")
                if consumer["old_patterns"]:
                    print(f"       Old Patterns: {', '.join(consumer['old_patterns'])}")
                if consumer["new_patterns"]:
                    print(f"       New Patterns: {', '.join(set(consumer['new_patterns']))}")

        print("\n" + "=" * 80)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Verify compliance endpoint usage across codebase")
    parser.add_argument(
        "--root-dir",
        type=str,
        default=None,
        help="Root directory to search (default: parent of script directory)",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--output", type=str, default=None, help="Output file for JSON report")

    args = parser.parse_args()

    verifier = ComplianceEndpointVerifier(root_dir=args.root_dir)

    # Search codebase
    references = verifier.search_codebase()
    print(f"Found {len(references)} endpoint references")

    # Verify consumers
    verifications = verifier.verify_all_consumers()
    print(f"Verified {len(verifications)} consumers")

    # Generate report
    report = verifier.generate_report()

    # Print or save report
    if args.json:
        output = json.dumps(report, indent=2)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
            print(f"\nJSON report saved to {args.output}")
        else:
            print(output)
    else:
        verifier.print_report(report)
        if args.output:
            with open(args.output, "w") as f:
                json.dump(report, f, indent=2)
            print(f"\nJSON report also saved to {args.output}")

    # Exit with error code if verification failed
    if report["summary"]["verification_status"] == "FAIL":
        exit(1)
    else:
        exit(0)


if __name__ == "__main__":
    main()
