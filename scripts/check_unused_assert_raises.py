#!/usr/bin/env python3
"""
GATE-02 — No unused assertRaises context managers.

Detects ``with self.assertRaises(SomeException) as cm:`` blocks where the
context variable (e.g. ``cm``) is never referenced **anywhere** in the
enclosing test function — not just inside the ``with`` body but also in
statements that follow the ``with`` block (such as
``self.assertEqual(str(cm.exception), ...)`` on the line after).

Uses AST to walk the entire enclosing function; the variable is considered
"used" if a ``ast.Name(id=var)`` node appears outside the ``with`` statement
itself (or inside the ``with`` body in a meaningful access pattern).

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
                if fn.startswith("test_") and fn.endswith(".py"):
                    files.append(os.path.join(dirpath, fn))
    return sorted(files)


def _enclosing_function(tree: ast.AST, lineno: int) -> ast.AST | None:
    """Find the function/method node that contains *lineno*."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.lineno <= lineno <= node.end_lineno:
                return node
    return None


def _var_used_outside_with(
    var_name: str,
    with_node: ast.With,
    enclosing_func: ast.AST,
) -> bool:
    """Return True if *var_name* is referenced anywhere in the enclosing
    function OUTSIDE the ``with`` node itself (i.e. before or after the
    ``with`` statement)."""
    for node in ast.walk(enclosing_func):
        if isinstance(node, ast.Name) and node.id == var_name:
            # Check if this Name node is inside the with_node
            inside_with = False
            for ancestor in ast.walk(with_node):
                if ancestor is node:
                    inside_with = True
                    break
            # If the Name node is inside the with body, we also count it as
            # used — accessing cm.exception inside the with block is valid.
            if not inside_with:
                # Check if it's inside the with_node (including body)
                for child in ast.walk(with_node):
                    if child is node:
                        inside_with = True
                        break
            if not _node_inside(node, with_node) or _node_inside_with_body(node, with_node):
                return True
    return False


def _node_inside(node: ast.AST, container: ast.AST) -> bool:
    """Return True if *node* is somewhere inside *container*'s AST subtree."""
    for child in ast.walk(container):
        if child is node:
            return True
    return False


def _node_inside_with_body(node: ast.AST, with_node: ast.With) -> bool:
    """Return True if *node* is inside the body statements of the with_node."""
    for stmt in with_node.body:
        for child in ast.walk(stmt):
            if child is node:
                return True
    return False


def _var_used_in_enclosing_function(
    var_name: str,
    with_node: ast.With,
    enclosing_func: ast.AST,
) -> bool:
    """Return True if *var_name* is referenced anywhere in the enclosing
    function — both inside the with-body AND in statements after the with
    block.

    The variable must appear AT LEAST ONCE outside of just being the target
    of the ``as`` clause itself.
    """
    for node in ast.walk(enclosing_func):
        if isinstance(node, ast.Name) and node.id == var_name:
            # Skip the Name node that IS the optional_vars target itself
            # (the 'as cm' part)
            if _is_optional_vars_target(node, with_node):
                continue
            return True
    return False


def _is_optional_vars_target(node: ast.Name, with_node: ast.With) -> bool:
    """Return True if *node* is the ``as cm`` target in the with statement."""
    for item in with_node.items:
        if item.optional_vars is node:
            return True
    return False


class ViolationFinder(ast.NodeVisitor):
    """Walk the AST collecting unused assertRaises contexts."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.violations: list[tuple[int, str]] = []
        self._tree: ast.AST | None = None

    def set_tree(self, tree: ast.AST) -> None:
        self._tree = tree

    def visit_With(self, node: ast.With) -> None:
        if self._tree is None:
            self.generic_visit(node)
            return

        for item in node.items:
            if not isinstance(item.optional_vars, ast.Name):
                continue
            ctx_var = item.optional_vars.id
            call = item.context_expr
            if not isinstance(call, ast.Call):
                continue
            if not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr != "assertRaises":
                continue

            # Find the enclosing function
            enclosing = _enclosing_function(self._tree, node.lineno)
            if enclosing is None:
                continue

            # Check if ctx_var is used anywhere in the enclosing function
            # (including after the with-block, like ctx.exception)
            if not _var_used_in_enclosing_function(ctx_var, node, enclosing):
                self.violations.append(
                    (
                        node.lineno,
                        f"assertRaises context variable '{ctx_var}' unused in enclosing function",
                    )
                )

        self.generic_visit(node)


def check_file(file_path: str) -> list[tuple[int, str]]:
    with open(file_path, encoding="utf-8") as fh:
        source = fh.read()
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return []
    visitor = ViolationFinder(file_path)
    visitor.set_tree(tree)
    visitor.visit(tree)
    return visitor.violations


def main() -> None:
    parser = argparse.ArgumentParser(description="GATE-02: No unused assertRaises context managers")
    parser.add_argument(
        "--path",
        nargs="*",
        default=None,
        help="Scope to specific directories (default: hub/ tests/).",
    )
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
