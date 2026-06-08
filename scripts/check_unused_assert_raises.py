#!/usr/bin/env python3
"""
GATE-02 — No unused assertRaises context managers.

Detects ``with self.assertRaises(SomeException) as cm:`` blocks where
*cm* is never referenced in the body (i.e. ``cm.exception`` is never
checked).  These tests verify that an exception is raised but never
inspect *which* exception or its attributes — a weaker assertion.

Scans ``hub/`` and ``tests/`` Python files.

Usage:
    python scripts/check_unused_assert_raises.py          # full scan
    python scripts/check_unused_assert_raises.py --path hub/apps/assets  # scoped

Exit 0 on clean, 1 if violations found.
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Maximum number of characters to scan in the with-body for a cm reference.
# A with-block longer than this is too large to reliably check.
MAX_BODY_LENGTH = 500


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


class AssertRaisesVisitor(ast.NodeVisitor):
    """Walk the AST collecting unused assertRaises contexts."""

    def __init__(self, file_path: str, source_lines: list[str]) -> None:
        self.file_path = file_path
        self.source_lines = source_lines
        self.violations: list[tuple[int, str]] = []

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            # Check for ``with self.assertRaises(...) as cm:``
            if not isinstance(item.optional_vars, ast.Name):
                continue
            ctx_var = item.optional_vars.id  # e.g. "cm"
            call = item.context_expr
            if not isinstance(call, ast.Call):
                continue
            if not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr != "assertRaises":
                continue

            # Now check whether *ctx_var* is used anywhere in the with-body.
            body_text = "".join(
                self.source_lines[node.body[0].lineno - 1: node.body[-1].end_lineno]
            ) if node.body else ""

            if len(body_text) > MAX_BODY_LENGTH:
                body_text = body_text[:MAX_BODY_LENGTH]

            if ctx_var not in body_text:
                self.violations.append((
                    node.lineno,
                    f"assertRaises context variable '{ctx_var}' unused in with-body",
                ))

        self.generic_visit(node)


def check_file(file_path: str) -> list[tuple[int, str]]:
    with open(file_path, encoding="utf-8") as fh:
        source = fh.read()
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return []
    lines = source.splitlines(keepends=True)
    visitor = AssertRaisesVisitor(file_path, lines)
    visitor.visit(tree)
    return visitor.violations


def main() -> None:
    parser = argparse.ArgumentParser(description="GATE-02: No unused assertRaises context managers")
    parser.add_argument("--path", nargs="*", default=None,
                        help="Scope to specific directories (default: hub/ tests/).")
    args = parser.parse_args()

    roots = args.path if args.path else [
        str(REPO_ROOT / "hub"),
        str(REPO_ROOT / "tests"),
    ]
    test_files = _find_test_files(roots)

    all_violations: list[tuple[str, int, str]] = []
    for fp in test_files:
        for lineno, msg in check_file(fp):
            all_violations.append((fp, lineno, msg))

    if all_violations:
        print(f"GATE-02: {len(all_violations)} unused assertRaises context(s) found:")
        for path, lineno, msg in all_violations[:20]:
            rel = os.path.relpath(path, REPO_ROOT)
            print(f"  {rel}:{lineno} — {msg}")
        if len(all_violations) > 20:
            print(f"  ... and {len(all_violations) - 20} more")
        sys.exit(1)

    print("GATE-02: PASSED — no unused assertRaises context managers found.")
    sys.exit(0)


if __name__ == "__main__":
    main()
