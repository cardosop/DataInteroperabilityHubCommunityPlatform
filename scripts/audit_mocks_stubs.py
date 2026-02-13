#!/usr/bin/env python3
"""
Audit script to identify and classify all mocks/stubs in test files.

Classification:
1. External boundary (third-party HTTP, external services) - keep with justification
2. Hub/services/DB - MUST be removed and replaced with real implementations
"""

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# Patterns to find mocks/stubs
MOCK_PATTERNS = [
    r"@patch\(",
    r"@patch\.",
    r"Mock\(",
    r"MagicMock\(",
    r"AsyncMock\(",
    r"\.mock\s*=",
    r"\.return_value\s*=",
    r"\.side_effect\s*=",
    r"patch\(",
    r"stub\(",
    r"@mock\.",
]

# External boundary patterns (acceptable mocks)
EXTERNAL_BOUNDARY_PATTERNS = [
    r"prefect",
    r"stripe",
    r"sendgrid",
    r"email",
    r"http\.client",
    r"requests\.",
    r"urllib\.",
    r"boto3",
    r"gcp",
    r"aws",
    r"third.?party",
    r"external",
    r"api\.client",
    r"httpx",
    r"aiohttp",
]

# Internal patterns (MUST be removed)
INTERNAL_PATTERNS = [
    r"hub\.apps\.",
    r"hub\.core\.",
    r"hub\.services\.",
    r"django\.db",
    r"django\.core\.cache",
    r"django\.contrib\.auth",
    r"get_user_model",
    r"\.objects\.",
    r"\.save\(",
    r"\.create\(",
    r"\.get\(",
    r"\.filter\(",
    r"TransactionTestCase",
    r"TestCase",
]


def find_mock_usage(file_path: Path) -> List[Dict]:
    """Find all mock/stub usage in a file."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return [{"error": str(e)}]

    results = []
    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        # Check for mock patterns
        for pattern in MOCK_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                # Classify the mock
                classification = classify_mock(line, content, line_num)
                results.append(
                    {
                        "line": line_num,
                        "content": line.strip(),
                        "pattern": pattern,
                        "classification": classification,
                        "file": str(file_path),
                    }
                )
                break

    return results


def classify_mock(line: str, full_content: str, line_num: int) -> str:
    """Classify a mock as external boundary or internal."""
    # Get context around the line
    start = max(0, line_num - 10)
    end = min(len(full_content.split("\n")), line_num + 10)
    context = "\n".join(full_content.split("\n")[start:end])

    # Check for external boundary patterns
    for pattern in EXTERNAL_BOUNDARY_PATTERNS:
        if re.search(pattern, context, re.IGNORECASE):
            return "external_boundary"

    # Check for internal patterns
    for pattern in INTERNAL_PATTERNS:
        if re.search(pattern, context, re.IGNORECASE):
            return "internal_must_remove"

    # Check if it's a middleware mock (acceptable for middleware testing)
    if "middleware" in context.lower() and "get_response" in context.lower():
        return "middleware_testing"

    # Default to unknown - needs manual review
    return "unknown_needs_review"


def audit_directory(directory: Path) -> Dict:
    """Audit all test files in a directory."""
    results = {
        "external_boundary": [],
        "internal_must_remove": [],
        "middleware_testing": [],
        "unknown_needs_review": [],
        "errors": [],
    }

    # Find all test files
    test_files = list(directory.rglob("test_*.py"))
    test_files.extend(directory.rglob("*_test.py"))

    for test_file in test_files:
        mock_usages = find_mock_usage(test_file)
        for usage in mock_usages:
            if "error" in usage:
                results["errors"].append(usage)
            else:
                classification = usage["classification"]
                results[classification].append(usage)

    return results


def main():
    """Main audit function."""
    project_root = Path(__file__).parent.parent

    # Priority apps to audit
    priority_apps = [
        "scheduled_ingestion",
        "auth",
        "jobs",
        "contracts",
        "assets",
        "billing",
        "tenants",
    ]

    all_results = {}

    # Audit hub/apps
    hub_apps = project_root / "hub" / "apps"
    for app_name in priority_apps:
        app_path = hub_apps / app_name / "tests"
        if app_path.exists():
            print(f"Auditing {app_name}...")
            results = audit_directory(app_path)
            all_results[app_name] = results

    # Audit tests/ directory
    tests_dir = project_root / "tests"
    if tests_dir.exists():
        print("Auditing tests/ directory...")
        all_results["tests"] = audit_directory(tests_dir)

    # Print summary
    print("\n" + "=" * 80)
    print("AUDIT SUMMARY")
    print("=" * 80)

    for app_name, results in all_results.items():
        print(f"\n{app_name.upper()}:")
        print(f"  External boundary (keep): {len(results['external_boundary'])}")
        print(f"  Internal (MUST remove): {len(results['internal_must_remove'])}")
        print(f"  Middleware testing (acceptable): {len(results['middleware_testing'])}")
        print(f"  Unknown (needs review): {len(results['unknown_needs_review'])}")
        print(f"  Errors: {len(results['errors'])}")

    # Save detailed results
    output_file = project_root / "mock_audit_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nDetailed results saved to: {output_file}")

    # Print internal mocks that MUST be removed
    print("\n" + "=" * 80)
    print("INTERNAL MOCKS THAT MUST BE REMOVED")
    print("=" * 80)

    for app_name, results in all_results.items():
        if results["internal_must_remove"]:
            print(f"\n{app_name.upper()}:")
            for usage in results["internal_must_remove"][:20]:  # Show first 20
                print(f"  {usage['file']}:{usage['line']}")
                print(f"    {usage['content'][:100]}")
            if len(results["internal_must_remove"]) > 20:
                print(f"  ... and {len(results['internal_must_remove']) - 20} more")


if __name__ == "__main__":
    main()
