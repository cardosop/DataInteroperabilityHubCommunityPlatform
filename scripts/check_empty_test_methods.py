#!/usr/bin/env python3
"""
GATE-08 — No empty test methods.

Detects ``def test_*()`` functions whose body contains only ``pass``,
``...``, a docstring with no assertions, or no executable statements.

An empty test method passes silently and provides zero value while
inflating coverage metrics.  Every test function must contain at
least one assertion or meaningful side-effect call.

v2 — Fixed duplicate-counting bug (visit_FunctionDef + visit_ClassDef
double-counted class methods).  Added missing meaningful-call prefixes
for helper delegation (``self._assert*``, ``self._verify*``, etc.) and
``self.skipTest``.  Inverted "meaningful" detection: any ``ast.Call``
is treated as meaningful unless it is a known no-op (bare ``pass``,
``Ellipsis``, or a docstring-only body).

Usage:
    python scripts/check_empty_test_methods.py
    python scripts/check_empty_test_methods.py --path hub/apps/assets/tests

Exit 0 on clean, 1 if violations found.
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Function calls that count as "meaningful" even without explicit assertions.
# This list is used as a FALLBACK for calls whose function name we cannot
# determine — any ``ast.Call`` is treated as meaningful by default.
# Known no-ops (``pass``, ``...``, docstrings, ``pytest.skip()`` without
# annotation) are handled separately.
MEANINGFUL_CALL_PREFIXES = {
    # Explicit unittest assertions
    "self.assert",
    # pytest-style assertions
    "assert",
    # Helper delegation patterns (self._assert_envelope(...), etc.)
    "self._assert",
    "self._verify",
    "self._check",
    "self._test",
    "self._run",
    "self._validate",
    # Legitimate test control-flow
    "self.skipTest",
    # Django test client
    "client.",
    # Factory / generator calls
    "create",
    "generate",
    "execute",
    "run",
    # Common verification helpers
    "validate",
    "check",
    # Response attribute access (response.status_code, etc.)
    "response",
    # pytest helpers
    "pytest.",
}

# Expressions that are NOT empty: control-flow nodes that indicate a meaningful
# test even without explicit function calls.
NON_EMPTY_NODES = (
    ast.Assert,       # bare assert
    ast.Assign,       # variable assignment
    ast.AugAssign,    # augmented assignment
    ast.AnnAssign,    # annotated assignment (x: int = 5)
    ast.Return,       # return statement
    ast.Yield,        # yield
    ast.YieldFrom,    # yield from
    ast.Raise,        # raise
    ast.For,          # for loop
    ast.AsyncFor,     # async for loop
    ast.While,        # while loop
    ast.With,         # with context manager
    ast.AsyncWith,    # async with context manager
    ast.Try,          # try/except
    ast.If,           # conditional
    ast.Import,       # bare import (module existence check)
    ast.ImportFrom,   # from-import (module existence check)
    ast.Delete,       # del statement
    ast.Global,       # global declaration
    ast.Nonlocal,     # nonlocal declaration
)


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


def _is_docstring(stmt: ast.stmt) -> bool:
    """Return True if *stmt* is a string-literal expression (docstring)."""
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return isinstance(stmt.value.value, str)
    return False


def _is_meaningful_call(stmt: ast.stmt) -> bool:
    """Return True if the statement is a function call that represents meaningful test activity.

    Any ``ast.Call`` is treated as meaningful UNLESS it is ``pytest.skip()``
    (which is flagged by GATE-07 separately).
    """
    if not isinstance(stmt, ast.Expr):
        return False
    if not isinstance(stmt.value, ast.Call):
        return False
    call = stmt.value

    # Determine the call's textual name.
    func_name = ""
    if isinstance(call.func, ast.Name):
        func_name = call.func.id
    elif isinstance(call.func, ast.Attribute):
        try:
            func_name = ast.unparse(call.func)
        except Exception:
            func_name = ""

    # Any call to a function whose name starts with one of the meaningful
    # prefixes is meaningful.
    for prefix in MEANINGFUL_CALL_PREFIXES:
        if func_name.startswith(prefix):
            return True

    # Any other call is ALSO treated as meaningful — it represents a
    # "does not raise" test or a side-effect call.
    # The only exceptions are known no-ops like bare ``pytest.skip()``
    # which we explicitly exclude.
    if func_name in ("pytest.skip",):
        return False

    # Everything else is meaningful.
    return True


def _is_empty_func(node: ast.FunctionDef) -> bool:
    """Check if the function body is effectively empty."""
    # Strip docstrings from the body.
    body = [s for s in node.body if not (isinstance(s, ast.Expr) and _is_docstring(s))]

    # Empty body (no statements after docstring).
    if not body:
        return True

    # Only ``pass``.
    if len(body) == 1 and isinstance(body[0], ast.Pass):
        return True

    # Only ``...`` (Ellipsis literal).
    if len(body) == 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if body[0].value.value is Ellipsis:
            return True

    # Check if ANY non-docstring statement is meaningful.
    for stmt in body:
        # Control-flow nodes (if, for, while, with, try, raise, etc.) are meaningful.
        if isinstance(stmt, NON_EMPTY_NODES):
            return False

        # Function calls — check if meaningful.
        if _is_meaningful_call(stmt):
            return False

    # No meaningful statements found.
    return True


class EmptyTestVisitor(ast.NodeVisitor):
    """Walk test classes and top-level test functions looking for empty methods.

    Uses separate paths for class-based tests (via visit_ClassDef) and
    top-level tests (via visit_Module) to avoid double-counting.
    """

    def __init__(self) -> None:
        self.violations: list[tuple[int, str]] = []
        self._class_stack: list[str] = []

    def visit_Module(self, node: ast.Module) -> None:
        """Check top-level ``def test_*`` functions (not inside a class)."""
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                if _is_empty_func(item):
                    self.violations.append((item.lineno, item.name))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Check ``def test_*`` methods inside a class whose name starts with 'Test'."""
        if node.name.startswith("Test"):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test_"):
                    if _is_empty_func(item):
                        self.violations.append((item.lineno, f"{node.name}.{item.name}"))
        # Do NOT call generic_visit inside the class to avoid visit_FunctionDef
        # walking the same methods again (duplicate-counting bug).


def check_file(file_path: str) -> list[tuple[int, str]]:
    with open(file_path, encoding="utf-8") as fh:
        source = fh.read()
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return []
    visitor = EmptyTestVisitor()
    visitor.visit(tree)
    return visitor.violations


def main() -> None:
    parser = argparse.ArgumentParser(description="GATE-08: No empty test methods")
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

    violations: list[tuple[str, int, str]] = []
    for fp in test_files:
        for lineno, func_name in check_file(fp):
            violations.append((fp, lineno, func_name))

    if violations:
        print(f"GATE-08: {len(violations)} empty test method(s) found:")
        for path, lineno, func_name in violations[:30]:
            rel = os.path.relpath(path, REPO_ROOT)
            print(f"  {rel}:{lineno} — {func_name}")
        if len(violations) > 30:
            print(f"  ... and {len(violations) - 30} more")
        print("Every test function must contain at least one assertion or meaningful call.")
        sys.exit(1)

    print("GATE-08: PASSED — no empty test methods found.")
    sys.exit(0)


if __name__ == "__main__":
    main()
