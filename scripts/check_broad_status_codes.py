#!/usr/bin/env python3
"""
GATE-03 — No broad status code lists.

Flags ``assertIn(status_code, [...])`` with more than 2 status codes.
Broad status-code assertions mask HTTP semantics — a test that accepts
200, 201, 204, and 301 is not testing a specific behaviour.

Scans ``hub/`` and ``tests/`` Python test files.

Usage:
    python scripts/check_broad_status_codes.py
    python scripts/check_broad_status_codes.py --max-codes 3

Exit 0 on clean, 1 if violations found.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Regex:  assertIn(status_code, [...])  or  self.assertIn(status_code, [...])
# where the first argument contains "status" (case-insensitive) indicating it's
# an HTTP status code check, not a general list-membership assertion.
# Matches multiline lists.
_ASSERT_STATUS_IN_LIST = re.compile(
    r"assertIn\(\s*\w*\.?\w*status\w*\s*,\s*\[([^\]]+)\]",
    re.DOTALL | re.IGNORECASE,
)


def _count_codes(list_body: str) -> int:
    """Count comma-separated items in a list body string."""
    if not list_body.strip():
        return 0
    return list_body.count(",") + 1


def _find_test_files(search_roots: list[str]) -> list[str]:
    files: list[str] = []
    for root in search_roots:
        p = Path(root)
        if not p.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(p):
            dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git", "migrations",
                                                             ".venv", "venv", "node_modules")]
            for fn in filenames:
                if fn.startswith("test_") and fn.endswith(".py"):
                    files.append(os.path.join(dirpath, fn))
    return sorted(files)


def check_file(file_path: str, max_codes: int) -> list[tuple[int, str, int]]:
    violations: list[tuple[int, str, int]] = []
    try:
        with open(file_path, encoding="utf-8") as fh:
            source = fh.read()
    except Exception:
        return violations

    for match in _ASSERT_STATUS_IN_LIST.finditer(source):
        list_body = match.group(1)
        count = _count_codes(list_body)
        if count > max_codes:
            lineno = source[: match.start()].count("\n") + 1
            violations.append((lineno, list_body.strip()[:80], count))

    return violations


def main() -> None:
    parser = argparse.ArgumentParser(description="GATE-03: No broad status code lists")
    parser.add_argument("--max-codes", type=int, default=2,
                        help="Maximum allowed status codes in assertIn list (default: 2).")
    parser.add_argument("--path", nargs="*", default=None,
                        help="Scope to specific directories.")
    args = parser.parse_args()

    roots = args.path if args.path else [
        str(REPO_ROOT / "hub"),
        str(REPO_ROOT / "tests"),
    ]
    test_files = _find_test_files(roots)

    all_violations: list[tuple[str, int, str, int]] = []
    for fp in test_files:
        for lineno, snippet, count in check_file(fp, args.max_codes):
            all_violations.append((fp, lineno, snippet, count))

    if all_violations:
        print(f"GATE-03: {len(all_violations)} broad status-code assertion(s) found "
              f"(>{args.max_codes} codes):")
        for path, lineno, snippet, count in all_violations[:20]:
            rel = os.path.relpath(path, REPO_ROOT)
            print(f"  {rel}:{lineno} — {count} codes: [{snippet}...]")
        if len(all_violations) > 20:
            print(f"  ... and {len(all_violations) - 20} more")
        sys.exit(1)

    print(f"GATE-03: PASSED — no assertIn with >{args.max_codes} status codes found.")
    sys.exit(0)


if __name__ == "__main__":
    main()
