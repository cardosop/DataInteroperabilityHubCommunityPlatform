#!/usr/bin/env python3
"""
Parse a pytest log (e.g. batch_11.log) and run only tests that FAILED, ERROR, or SKIPPED.

Usage:
  python scripts/run_failed_error_skipped_from_log.py path/to/batch_11.log
  python scripts/run_failed_error_skipped_from_log.py path/to/batch_11.log -- -v --tb=short   # pass args to pytest (use --)
  python scripts/run_failed_error_skipped_from_log.py path/to/batch_11.log --skip  # exclude skipped, run only failed/error
  python scripts/run_failed_error_skipped_from_log.py path/to/batch_11.log --dry-run  # print test IDs only

Exit code: same as pytest (0 if all selected tests pass).
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


def parse_log(log_path: Path, include_skipped: bool = True) -> list[str]:
    """Extract test node IDs that ended with FAILED, ERROR, or (optionally) SKIPPED."""
    text = log_path.read_text()
    # Line format: "path/to/file.py::TestClass::test_method FAILED [ 13%]"
    pattern = re.compile(
        r"^(tests/[^\s]+)\s+(FAILED|ERROR|SKIPPED)(?:\s+\[.*\])?$", re.MULTILINE
    )
    out = []
    for m in pattern.finditer(text):
        node_id, status = m.group(1), m.group(2)
        if status in ("FAILED", "ERROR"):
            out.append(node_id)
        elif include_skipped and status == "SKIPPED":
            out.append(node_id)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_file", type=Path, help="Path to pytest log (e.g. batch_11.log)")
    parser.add_argument(
        "--skip",
        action="store_true",
        help="Exclude SKIPPED tests; run only FAILED and ERROR",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print test IDs only, do not run pytest",
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Extra args for pytest. Use -- to separate from script args (e.g. -- -v --tb=short)",
    )
    args = parser.parse_args()

    if not args.log_file.exists():
        print(f"Error: log file not found: {args.log_file}", file=sys.stderr)
        return 1

    node_ids = parse_log(args.log_file, include_skipped=not args.skip)
    if not node_ids:
        print("No FAILED/ERROR/SKIPPED tests found in log.", file=sys.stderr)
        return 0

    print(f"Found {len(node_ids)} test(s) to run (FAILED/ERROR" + ("" if args.skip else "/SKIPPED") + ").")
    for n in node_ids:
        print(f"  {n}")

    if args.dry_run:
        return 0

    cmd = [sys.executable, "-m", "pytest"] + node_ids + args.pytest_args
    return subprocess.run(cmd, cwd=Path(__file__).resolve().parent.parent).returncode


if __name__ == "__main__":
    sys.exit(main())
