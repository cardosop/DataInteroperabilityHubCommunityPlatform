#!/usr/bin/env python3
"""
285.14.6.7 — CI-ASSERT-REAL gate.

Scans test files for placeholder assertions that indicate a test was stubbed
but never implemented:

  - ``assertTrue(True)`` — trivially true, masks missing logic (always a violation)
  - ``assertIsNotNone(response)`` when it is the ONLY assertion in a test method
    (i.e. the test doesn't actually verify anything about the response)

Uses AST parsing so that ``assertIsNotNone(response)`` followed by further
assertions (status code, body fields, headers, etc.) is NOT flagged — the
naive line-by-line regex was producing 36 false positives because it couldn't
see assertions on subsequent lines.

Exit 0 on clean, 1 if violations found.
"""

import ast
import os
import sys


def _is_test_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True if the function is a test (starts with ``test_``)."""
    return node.name.startswith("test_")


def _is_assert_call(node: ast.AST) -> bool:
    """Return True if the node is an assertion call expression."""
    if not isinstance(node, ast.Expr):
        return False
    call = node.value
    if not isinstance(call, ast.Call):
        return False
    # self.assertXxx(...)
    if isinstance(call.func, ast.Attribute):
        return call.func.attr.startswith("assert")
    # bare assertXxx(...) — pytest-style
    if isinstance(call.func, ast.Name):
        return call.func.id.startswith("assert")
    return False


def _assert_name(node: ast.Expr) -> str:
    """Extract the assertion method name (e.g. 'assertIsNotNone', 'assertEqual')."""
    call = node.value
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return ""


def _assert_args_str(node: ast.Expr) -> str:
    """Reconstruct the argument source text from an assertion call node."""
    call = node.value
    parts = []
    for arg in call.args:
        try:
            parts.append(ast.unparse(arg))
        except Exception:
            parts.append("<?>")
    return ", ".join(parts)


def _is_bare_response_check(assert_name: str, args_str: str) -> bool:
    """Check if an assertion is a bare ``assertIsNotNone(response)``."""
    if assert_name not in ("assertIsNotNone",):
        return False
    # Match 'response' or 'self.response' or 'response, ...'
    return "response" in args_str


def _is_assert_true_true(assert_name: str, args_str: str) -> bool:
    """Check if an assertion is ``assertTrue(True)`` (trivially true)."""
    if assert_name not in ("assertTrue",):
        return False
    return args_str.strip() == "True"


def analyze_file(filepath: str) -> list[tuple[int, str]]:
    """Parse a test file and find stub/placeholder assertions.

    Returns a list of (lineno, description) tuples for each violation.
    """
    try:
        with open(filepath) as fh:
            source = fh.read()
        tree = ast.parse(source)
    except SyntaxError:
        return []

    violations: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _is_test_function(node):
            continue

        # Collect all assert call expressions within this test function.
        assert_calls: list[ast.Expr] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Expr) and _is_assert_call(child):
                assert_calls.append(child)

        # Check for trivially-true assertions (always a violation).
        for ac in assert_calls:
            name = _assert_name(ac)
            args_str = _assert_args_str(ac)
            if _is_assert_true_true(name, args_str):
                violations.append((ac.lineno, "assertTrue(True) — trivially true"))

        # Check for bare assertIsNotNone(response) — only a violation when it
        # is the SOLE assertion in the test method.
        if len(assert_calls) == 1:
            ac = assert_calls[0]
            name = _assert_name(ac)
            args_str = _assert_args_str(ac)
            if _is_bare_response_check(name, args_str):
                violations.append(
                    (ac.lineno, f"bare {name}(response) — only assertion in {node.name}()"),
                )

    return violations


def main() -> int:
    violations: list[tuple[str, int, str]] = []

    for root, dirs, files in os.walk("hub/apps"):
        dirs[:] = [d for d in dirs if d not in ("migrations", "__pycache__", ".git")]
        for f in files:
            if not f.startswith("test_") or not f.endswith(".py"):
                continue
            path = os.path.join(root, f)
            for lineno, desc in analyze_file(path):
                violations.append((path, lineno, desc))

    if violations:
        print(f"ASSERT-REAL gate: {len(violations)} violation(s) found:")
        for path, lineno, desc in violations[:20]:
            print(f"  {path}:{lineno} — {desc}")
        if len(violations) > 20:
            print(f"  ... and {len(violations) - 20} more")
        return 1

    print("ASSERT-REAL gate: PASSED — no trivially-true assertions found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
