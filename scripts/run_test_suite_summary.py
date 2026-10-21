#!/usr/bin/env python3
"""
Generate a summary of test execution results from log files.
"""

import re
import sys
from pathlib import Path


def extract_pytest_summary(log_content: str) -> dict[str, int]:
    """Extract pytest summary from log content."""
    summary = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
    }

    # Look for pytest summary line
    lines = log_content.split("\n")
    for line in reversed(lines):
        # Match: "X passed, Y failed, Z skipped in N.NNs"
        if re.search(r"\d+\s+(passed|failed|skipped|error)", line) and (
            "in " in line or "warnings" in line.lower()
        ):
            passed_match = re.search(r"(\d+)\s+passed", line)
            if passed_match:
                summary["passed"] = int(passed_match.group(1))

            failed_match = re.search(r"(\d+)\s+failed", line)
            if failed_match:
                summary["failed"] = int(failed_match.group(1))

            skipped_match = re.search(r"(\d+)\s+skipped", line)
            if skipped_match:
                summary["skipped"] = int(skipped_match.group(1))

            error_match = re.search(r"(\d+)\s+error", line)
            if error_match:
                summary["errors"] = int(error_match.group(1))

            summary["total"] = (
                summary["passed"] + summary["failed"] + summary["skipped"] + summary["errors"]
            )
            break

    return summary


def main():
    """Generate summary from latest test run log."""
    log_dir = Path("/tmp")
    log_files = sorted(
        log_dir.glob("full_test_suite_*.log"), key=lambda p: p.stat().st_mtime, reverse=True
    )

    if not log_files:
        print("No test log files found in /tmp")
        return 1

    latest_log = log_files[0]
    print(f"Analyzing: {latest_log}")

    with open(latest_log) as f:
        content = f.read()

    # Extract summaries for each category
    categories = {}
    current_category = None

    for line in content.split("\n"):
        if "CATEGORY:" in line:
            current_category = line.split("CATEGORY:")[-1].strip()
        elif current_category and (
            "passed" in line.lower() or "failed" in line.lower() or "error" in line.lower()
        ):
            # Try to extract summary from this section
            section_content = content[
                content.find(f"CATEGORY: {current_category}") : content.find(
                    "CATEGORY:", content.find(f"CATEGORY: {current_category}") + 1
                )
                if "CATEGORY:" in content[content.find(f"CATEGORY: {current_category}") + 1 :]
                else len(content)
            ]
            categories[current_category] = extract_pytest_summary(section_content)

    print("\nTest Execution Summary:")
    print("=" * 80)
    for category, summary in categories.items():
        print(f"\n{category}:")
        print(f"  Total: {summary['total']}")
        print(f"  Passed: {summary['passed']}")
        print(f"  Failed: {summary['failed']}")
        print(f"  Errors: {summary['errors']}")
        print(f"  Skipped: {summary['skipped']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
