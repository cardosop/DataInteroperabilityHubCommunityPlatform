#!/usr/bin/env python3
"""
GATE-06 — No ``try/except NoReverseMatch`` in tests.

Django's ``NoReverseMatch`` should never be caught in test code —
URL name mismatches are bugs that tests should surface, not hide.

Usage:
    python scripts/check_no_reverse_match.py
    python scripts/check_no_reverse_match.py --path hub/apps/assets/tests

Exit 0 on clean, 1 if violations found.
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _find_test_files(search_roots: list[str]) -> list[str]:
    files: list[str] = []
    for root in search_roots:
        p = Path(root)
        if not p.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(p):
            dirnames[:] = [
                d
                for d in dirnames
                if d not in ("__pycache__", ".git", "migrations", ".venv", "venv", "node_modules")
            ]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                if fn.startswith("test_") or fn.endswith("_test.py") or fn == "tests.py":
                    files.append(os.path.join(dirpath, fn))
    return sorted(files)


class NoReverseMatchVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.violations: list[int] = []

    def __init__(self, file_path: str, source_lines: list[str]) -> None:
        self.file_path = file_path
        self.source_lines = source_lines
        self.violations: list[int] = []

    def _has_noqa(self, lineno: int) -> bool:
        """Check if the current or previous line has a noqa annotation."""
        for offset in (0, 1):
            idx = lineno - 1 - offset
            if 0 <= idx < len(self.source_lines):
                if "# noqa: no-reverse-match" in self.source_lines[idx]:
                    return True
        return False

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            return
        if isinstance(node.type, ast.Name) and node.type.id == "NoReverseMatch":
            if not self._has_noqa(node.lineno):
                self.violations.append(node.lineno)
        elif isinstance(node.type, ast.Tuple):
            for elt in node.type.elts:
                if isinstance(elt, ast.Name) and elt.id == "NoReverseMatch":
                    if not self._has_noqa(node.lineno):
                        self.violations.append(node.lineno)
                    break
        self.generic_visit(node)


def check_file(file_path: str) -> list[int]:
    with open(file_path, encoding="utf-8") as fh:
        source = fh.read()
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return []
    visitor = NoReverseMatchVisitor(file_path, source.splitlines(keepends=True))
    visitor.visit(tree)
    return visitor.violations


def main() -> None:
    parser = argparse.ArgumentParser(description="GATE-06: No try/except NoReverseMatch in tests")
    parser.add_argument("--path", nargs="*", default=None)
    args = parser.parse_args()

    roots = (
        args.path
        if args.path
        else [
            str(REPO_ROOT / "hub"),
            str(REPO_ROOT / "tests"),
        ]
    )
    test_files = _find_test_files(roots)

    violations: list[tuple[str, int]] = []
    for fp in test_files:
        for lineno in check_file(fp):
            violations.append((fp, lineno))

    if violations:
        print(f"GATE-06: {len(violations)} try/except NoReverseMatch occurrence(s) found:")
        for path, lineno in violations[:20]:
            rel = os.path.relpath(path, REPO_ROOT)
            print(f"  {rel}:{lineno}")
        if len(violations) > 20:
            print(f"  ... and {len(violations) - 20} more")
        print("Remove try/except NoReverseMatch — URL name bugs should surface, not hide.")
        sys.exit(1)

    print("GATE-06: PASSED — no try/except NoReverseMatch found in tests.")
    sys.exit(0)


if __name__ == "__main__":
    main()
