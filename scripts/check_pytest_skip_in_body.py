#!/usr/bin/env python3
"""
GATE-07 — No ``pytest.skip()`` inside test function bodies.

``pytest.skip()`` inside a ``def test_*`` body skips the test at
runtime, which means the codepath up to the skip point runs during
collection and the reason is invisible until the test is executed.

Use ``@pytest.mark.skip(reason=...)`` or ``@pytest.mark.skipif(cond, reason=...)``
at the decorator level instead — these are visible at collection time.

Usage:
    python scripts/check_pytest_skip_in_body.py
    python scripts/check_pytest_skip_in_body.py --path hub/apps/assets/tests

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
            dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git", "migrations",
                                                             ".venv", "venv", "node_modules")]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                if fn.startswith("test_") or fn.endswith("_test.py") or fn == "tests.py":
                    files.append(os.path.join(dirpath, fn))
    return sorted(files)


class PytestSkipInBodyVisitor(ast.NodeVisitor):
    """Walk test functions looking for pytest.skip() calls in their body."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.violations: list[int] = []  # line numbers
        self._in_test_func = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name.startswith("test_"):
            was_in = self._in_test_func
            self._in_test_func = True
            for stmt in node.body:
                self._check_stmt(stmt)
            self._in_test_func = was_in
        self.generic_visit(node)

    def _check_stmt(self, node: ast.AST) -> None:
        """Recursively check a statement for pytest.skip() calls."""
        if not self._in_test_func:
            return
        # Direct call:  pytest.skip(...)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "pytest"
                and call.func.attr == "skip"
            ):
                self.violations.append(node.lineno)
                return
        # Conditional:  if cond: pytest.skip(...)
        if isinstance(node, ast.If):
            for stmt in node.body:
                self._check_stmt(stmt)
            for stmt in node.orelse:
                self._check_stmt(stmt)


def check_file(file_path: str) -> list[int]:
    with open(file_path, encoding="utf-8") as fh:
        source = fh.read()
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return []
    visitor = PytestSkipInBodyVisitor(file_path)
    visitor.visit(tree)
    return visitor.violations


def main() -> None:
    parser = argparse.ArgumentParser(description="GATE-07: No pytest.skip() in test bodies")
    parser.add_argument("--path", nargs="*", default=None)
    args = parser.parse_args()

    roots = args.path if args.path else [
        str(REPO_ROOT / "hub"),
        str(REPO_ROOT / "tests"),
    ]
    test_files = _find_test_files(roots)

    violations: list[tuple[str, int]] = []
    for fp in test_files:
        for lineno in check_file(fp):
            violations.append((fp, lineno))

    if violations:
        print(f"GATE-07: {len(violations)} pytest.skip() call(s) inside test bodies found:")
        for path, lineno in violations[:20]:
            rel = os.path.relpath(path, REPO_ROOT)
            print(f"  {rel}:{lineno}")
        if len(violations) > 20:
            print(f"  ... and {len(violations) - 20} more")
        print("Use @pytest.mark.skip(reason=...) or @pytest.mark.skipif(...) at the decorator level.")
        sys.exit(1)

    print("GATE-07: PASSED — no pytest.skip() inside test function bodies.")
    sys.exit(0)


if __name__ == "__main__":
    main()
