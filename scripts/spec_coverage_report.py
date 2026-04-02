#!/usr/bin/env python3
"""
Spec-to-Test Traceability Report

Scans test files for @pytest.mark.spec markers and generates
a coverage report showing which spec requirements have tests.

Usage:
    python scripts/spec_coverage_report.py
"""
import os
import re
import sys
from collections import defaultdict


def find_spec_markers(root_dir: str) -> dict:
    """Find all @pytest.mark.spec markers in test files."""
    specs = defaultdict(list)

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.startswith("test_") and filename.endswith(".py"):
                filepath = os.path.join(dirpath, filename)
                try:
                    with open(filepath, "r") as f:
                        content = f.read()
                except Exception:
                    continue

                # Find @pytest.mark.spec("...") markers
                for match in re.finditer(
                    r'@pytest\.mark\.spec\(["\']([^"\']+)["\']\)', content
                ):
                    spec_id = match.group(1)
                    # Find the test method name after this marker
                    pos = match.end()
                    method_match = re.search(
                        r"def (test_\w+)", content[pos : pos + 200]
                    )
                    test_name = (
                        method_match.group(1) if method_match else "unknown"
                    )
                    rel_path = os.path.relpath(filepath, root_dir)
                    specs[spec_id].append(f"{rel_path}::{test_name}")

    return dict(specs)


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    search_dirs = [
        os.path.join(root, "hub", "apps"),
        os.path.join(root, "tests"),
    ]

    all_specs = {}
    for d in search_dirs:
        if os.path.exists(d):
            all_specs.update(find_spec_markers(d))

    if not all_specs:
        print("No @pytest.mark.spec markers found.")
        print(
            "Add markers like: @pytest.mark.spec('billing:B1:fail-closed')"
        )
        sys.exit(0)

    print(f"Spec Coverage Report ({len(all_specs)} specs traced)")
    print("=" * 60)
    for spec_id in sorted(all_specs.keys()):
        tests = all_specs[spec_id]
        print(f"\n{spec_id} ({len(tests)} test(s)):")
        for test in tests:
            print(f"  - {test}")


if __name__ == "__main__":
    main()
