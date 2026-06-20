#!/usr/bin/env python3
"""
GATE-09 — No bare ``mock.assert_called()``.

``mock.assert_called()`` only checks that a mock was called at least
once — it does NOT verify what arguments were passed.  This is a
weak assertion that passes even when the mock is called with wrong
or unexpected data.

Use ``mock.assert_called_once_with(arg1, arg2, ...)`` with the
specific expected arguments, or ``mock.assert_called_with(...)``
for multiple-call scenarios.

Scans ``hub/`` and ``tests/`` Python test files.

Usage:
    python scripts/check_bare_assert_called.py
    python scripts/check_bare_assert_called.py --path hub/apps/assets/tests

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


class BareAssertCalledVisitor(ast.NodeVisitor):
    """Find ``.assert_called()`` calls (with no arguments)."""

    def __init__(self) -> None:
        self.violations: list[int] = []

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "assert_called":
            # ``.assert_called()`` with zero args is the bare form.
            if not node.args and not node.keywords:
                self.violations.append(node.lineno)
        self.generic_visit(node)


def check_file(file_path: str) -> list[int]:
    with open(file_path, encoding="utf-8") as fh:
        source = fh.read()
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return []
    visitor = BareAssertCalledVisitor()
    visitor.visit(tree)
    return visitor.violations


def main() -> None:
    parser = argparse.ArgumentParser(description="GATE-09: No bare mock.assert_called()")
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
        print(f"GATE-09: {len(violations)} bare assert_called() call(s) found:")
        for path, lineno in violations[:20]:
            rel = os.path.relpath(path, REPO_ROOT)
            print(f"  {rel}:{lineno}")
        if len(violations) > 20:
            print(f"  ... and {len(violations) - 20} more")
        print("Use assert_called_once_with(...) or assert_called_with(...) with specific args.")
        sys.exit(1)

    print("GATE-09: PASSED — no bare assert_called() found.")
    sys.exit(0)


if __name__ == "__main__":
    main()
