#!/usr/bin/env python3
"""
280.C.3.1 — CI scanner: count pytest.mark.skip usage per test file.
Alerts when any test file exceeds 5% skip rate.

Usage:
    python scripts/check_skip_usage.py [--threshold 5] [--ci]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_THRESHOLD = 5.0  # percent

SKIP_PATTERNS = (
    "@pytest.mark.skip",
    "@pytest.mark.skipif",
    "pytest.skip(",
    "pytest.xfail",
    "unittest.skip(",
    "unittest.skipIf(",
)

TEST_DIRS = ("tests/", "cli/tests/", "sdk/python/tests/", "hub/")


def count_tests_and_skips(filepath: Path) -> tuple[int, int]:
    """Return (total_test_functions, skipped_test_functions) for a file."""
    try:
        content = filepath.read_text()
    except Exception:
        return 0, 0

    lines = content.split("\n")
    total = sum(1 for line in lines if line.strip().startswith("def test_"))
    skips = sum(
        1 for line in lines
        if any(pattern in line for pattern in SKIP_PATTERNS)
    )
    return total, skips


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan test skip usage")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"Max skip percentage (default: {DEFAULT_THRESHOLD}%%)")
    parser.add_argument("--ci", action="store_true", help="CI mode: exit 1 on violation")
    args = parser.parse_args()

    violations: list[tuple[str, float, int, int]] = []

    for test_dir in TEST_DIRS:
        if not Path(test_dir).is_dir():
            continue
        for py_file in sorted(Path(test_dir).rglob("test_*.py")):
            total, skips = count_tests_and_skips(py_file)
            if total == 0:
                continue
            pct = (skips / total) * 100
            if pct > args.threshold:
                violations.append((str(py_file), pct, total, skips))

    if not violations:
        print(f"All test files within {args.threshold}% skip rate.")
        return 0

    print(f"Files exceeding {args.threshold}% skip rate threshold:")
    print(f"{'File':<70} {'Tests':>6} {'Skips':>6} {'Rate':>7}")
    print("-" * 93)
    for path, pct, total, skips in sorted(violations, key=lambda x: x[1], reverse=True):
        print(f"{path:<70} {total:>6} {skips:>6} {pct:>6.1f}%")

    if args.ci:
        print(f"\nCI gate: FAILED — {len(violations)} file(s) exceed threshold.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
