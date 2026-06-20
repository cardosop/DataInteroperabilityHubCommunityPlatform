#!/usr/bin/env python3
"""
GATE-04 — No tautological frontend DOM assertions.

Detects assertions that always pass and provide zero test value:

  - ``expect(document.body).toBeTruthy()`` — always true in JSDOM
  - ``expect(container).toBeTruthy()`` — already guaranteed by render()
  - ``expect(true).toBe(true)`` — trivially true
  - ``expect(false).toBe(false)`` — trivially true
  - ``expect(null).toBeNull()`` — trivially true
  - ``expect(undefined).toBeUndefined()`` — trivially true

Scans ``frontend/src/`` for ``*.test.ts``, ``*.test.tsx``, ``*.spec.ts``, ``*.spec.tsx``.

Usage:
    python scripts/check_tautological_frontend_assertions.py
    python scripts/check_tautological_frontend_assertions.py --path frontend/src/components

Exit 0 on clean, 1 if violations found.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

TAUTOLOGICAL_PATTERNS = [
    (
        r"expect\(\s*document\.body\s*\)\s*\.\s*toBeTruthy\s*\(\s*\)",
        "expect(document.body).toBeTruthy() — always true in JSDOM",
    ),
    (
        r"expect\(\s*container\s*\)\s*\.\s*toBeTruthy\s*\(\s*\)",
        "expect(container).toBeTruthy() — guaranteed by render()",
    ),
    (
        r"expect\(\s*true\s*\)\s*\.\s*toBe\s*\(\s*true\s*\)",
        "expect(true).toBe(true) — trivially true",
    ),
    (
        r"expect\(\s*false\s*\)\s*\.\s*toBe\s*\(\s*false\s*\)",
        "expect(false).toBe(false) — trivially true",
    ),
    (
        r"expect\(\s*null\s*\)\s*\.\s*toBeNull\s*\(\s*\)",
        "expect(null).toBeNull() — trivially true",
    ),
    (
        r"expect\(\s*undefined\s*\)\s*\.\s*toBeUndefined\s*\(\s*\)",
        "expect(undefined).toBeUndefined() — trivially true",
    ),
]

_NOQA_RE = re.compile(r"//\s*noqa:\s*tautological-assertion")


def _find_frontend_test_files(search_roots: list[str]) -> list[str]:
    """Find *.test.{ts,tsx} and *.spec.{ts,tsx} files."""
    files: list[str] = []
    for root in search_roots:
        p = Path(root)
        if not p.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(p):
            dirnames[:] = [
                d
                for d in dirnames
                if d not in ("node_modules", ".git", "dist", "build", "__pycache__")
            ]
            for fn in filenames:
                if (
                    fn.endswith(".test.ts")
                    or fn.endswith(".test.tsx")
                    or fn.endswith(".spec.ts")
                    or fn.endswith(".spec.tsx")
                ):
                    files.append(os.path.join(dirpath, fn))
    return sorted(files)


def check_file(file_path: str) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []
    try:
        with open(file_path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception:
        return violations

    for i, line in enumerate(lines):
        if _NOQA_RE.search(line):
            continue
        for pattern, desc in TAUTOLOGICAL_PATTERNS:
            if re.search(pattern, line):
                violations.append((i + 1, desc))
                break
    return violations


def main() -> None:
    parser = argparse.ArgumentParser(description="GATE-04: No tautological frontend assertions")
    parser.add_argument("--path", nargs="*", default=None)
    args = parser.parse_args()

    roots = (
        args.path
        if args.path
        else [
            str(REPO_ROOT / "frontend/src"),
        ]
    )
    test_files = _find_frontend_test_files(roots)

    all_violations: list[tuple[str, int, str]] = []
    for fp in test_files:
        for lineno, desc in check_file(fp):
            all_violations.append((fp, lineno, desc))

    if all_violations:
        print(f"GATE-04: {len(all_violations)} tautological assertion(s) found:")
        for path, lineno, desc in all_violations[:20]:
            rel = os.path.relpath(path, REPO_ROOT)
            print(f"  {rel}:{lineno} — {desc}")
        if len(all_violations) > 20:
            print(f"  ... and {len(all_violations) - 20} more")
        sys.exit(1)

    print("GATE-04: PASSED — no tautological frontend assertions found.")
    sys.exit(0)


if __name__ == "__main__":
    main()
