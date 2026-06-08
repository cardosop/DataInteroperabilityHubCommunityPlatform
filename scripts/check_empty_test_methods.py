#!/usr/bin/env python3
"""
GATE-08 — No empty test methods.

Detects ``def test_*()`` functions whose body contains only ``pass``,
``...``, a docstring with no assertions, or no executable statements.

An empty test method passes silently and provides zero value while
inflating coverage metrics.  Every test function must contain at
least one assertion or meaningful side-effect call.

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
# e.g. ``create_test_data()`` followed by assertions in a helper is fine.
# But a bare test that only calls a no-op helper is still suspicious.
MEANINGFUL_CALL_PREFIXES = {
    "assert",     # all assert_* calls
    "self.assert",  # unittest-style
    "pytest.",     # pytest.raises, pytest.fail, etc.
    "client.",     # Django test client calls
    "response",    # response.status_code, etc.
    "create",      # factory create_* calls
    "generate",    # data generation
    "verify",      # verification helpers
    "validate",    # validation helpers
    "check",       # check helpers
    "execute",     # command execution
    "run",         # runner calls
}

# Expressions that are NOT empty: yield, return, assignments, etc.
NON_EMPTY_NODES = (
    ast.Assert,       # bare assert
    ast.Assign,       # variable assignment
    ast.AugAssign,    # augmented assignment
    ast.Return,       # return statement
    ast.Yield,        # yield
    ast.YieldFrom,    # yield from
    ast.Raise,        # raise
    ast.For,          # for loop
    ast.While,        # while loop
    ast.With,         # with context
    ast.Try,          # try/except
    ast.If,           # conditional
)


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


def _is_empty_func(node: ast.FunctionDef) -> bool:
    """Check if the function body is effectively empty."""
    body = [s for s in node.body if not isinstance(s, ast.Expr) or not _is_docstring(s)]

    if not body:
        return True
    if len(body) == 1 and isinstance(body[0], ast.Pass):
        return True
    if len(body) == 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if body[0].value.value is Ellipsis:  # `...`
            return True

    # Check if ALL non-docstring statements are meaningful.
    has_meaningful = False
    for stmt in body:
        if isinstance(stmt, NON_EMPTY_NODES):
            has_meaningful = True
            break
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            # Check function name prefix.
            func_name = ""
            if isinstance(call.func, ast.Name):
                func_name = call.func.id
            elif isinstance(call.func, ast.Attribute):
                func_name = ast.unparse(call.func)
            for prefix in MEANINGFUL_CALL_PREFIXES:
                if func_name.startswith(prefix):
                    has_meaningful = True
                    break
            if has_meaningful:
                break

    return not has_meaningful


def _is_docstring(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return isinstance(stmt.value.value, str)
    return False


class EmptyTestVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: list[tuple[int, str]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name.startswith("test_") and _is_empty_func(node):
            self.violations.append((node.lineno, node.name))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name.startswith("Test"):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                    if _is_empty_func(item):
                        self.violations.append((item.lineno, f"{node.name}.{item.name}"))
        self.generic_visit(node)


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

    roots = args.path if args.path else [
        str(REPO_ROOT / "hub"),
        str(REPO_ROOT / "tests"),
    ]
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
