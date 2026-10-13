#!/usr/bin/env python3
"""GATE-39 — zero-assertion test checker (Phase T.1 / W13).

A test function with NO assertion passes vacuously: the function under
test can return None, raise, or regress, and the suite stays green. The
paid-tree vacuity audit (Phase P.9) fixed the known sites by hand; this
gate pins the CLASS with a ratcheted count.

What counts as an assertion (intraprocedural — see the limitation note):
``assert`` statements, ``self.assert*`` / ``self.fail*`` (unittest),
``pytest.raises`` / ``pytest.fail`` / ``pytest.warns``, and mock assertion
calls (``.assert_called*`` / ``.assert_not_called`` /
``.assert_has_calls``). Everything else — bare calls, side effects,
returns — leaves the function assert-free and counted.

LIMITATION (documented rather than mis-reported): the analysis is
INTRAPROCEDURAL — a test whose assertions live in a helper counts as
assert-free. This OVER-counts (the count is an upper bound on the true
number of vacuous tests), and the gate only fails on GROWTH, so the
limitation can only cause a false FAIL on a legitimate new
helper-asserting test, never a false PASS. The baseline therefore absorbs
the existing helper-asserting tests; converting one to inline assertions
only ever lowers the count.

Ratchet semantics (same shape as GATE-35): the count must not exceed the
committed baseline (``scripts/zero_assertion_baseline.json``); run
``--update`` to record a new floor after a fix wave.

Exit codes: 0 clean, 1 growth, 2 usage error.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_BASELINE = Path(__file__).resolve().parent / "zero_assertion_baseline.json"
DEFAULT_ROOTS = ["hub", "tests", "cli/tests", "scripts/tests", "services"]
_SKIP_DIRS = {
    "migrations",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "site-packages",
    "dist",
    "build",
    ".git",
}

# pytest assertion-introducing calls (Name or Attribute call targets).
_ASSERT_CALL_NAMES = {
    "pytest.raises",
    "pytest.fail",
    "pytest.warns",
    "pytest.deprecated_call",
    "fail",
    "raises",
    "warns",
}
# unittest-style: self.<name> where <name> starts with these prefixes.
_SELF_PREFIXES = ("assert", "fail")
# mock-style attribute chains ending in these (e.g. m.run.assert_called_once_with).
_MOCK_SUFFIXES = (
    "assert_called",
    "assert_not_called",
    "assert_has_calls",
    "assert_any_call",
    "assert_awaited",
)


def _is_test_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return node.name.startswith("test")


def _call_name(call: ast.Call) -> tuple[str, str] | None:
    """Return (scope, name) for assertion-shaped call targets."""
    if isinstance(call.func, ast.Attribute):
        return ("attr", call.func.attr)
    if isinstance(call.func, ast.Name):
        return ("name", call.func.id)
    return None


def _contains_assertion(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Intraprocedural scan of ONE test function for any assertion."""
    for child in ast.walk(func_node):
        if isinstance(child, ast.Assert):
            return True
        if not isinstance(child, ast.Call):
            continue
        target = _call_name(child)
        if target is None:
            continue
        scope, name = target
        # Bare assertXxx(...) — pytest style; pytest.raises/fail/warns as
        # bare names (monkeypatched into the module namespace).
        if scope == "name" and (name in _ASSERT_CALL_NAMES or name.startswith("assert")):
            return True
        if scope == "attr" and (
            name.startswith(_SELF_PREFIXES)
            or name.startswith(_MOCK_SUFFIXES)
            # mock chains: anything.call.assert_called_once_with(...)
            or name.startswith("assert_")
            or (
                # pytest-qualified assertion calls: the
                # `with pytest.raises(...)` context form is an Attribute
                # on the pytest module — catch it narrowly so unrelated
                # obj.fail() calls are NOT mis-counted.
                name in _ASSERT_CALL_NAMES
                and isinstance(child.func, ast.Attribute)
                and isinstance(child.func.value, ast.Name)
                and child.func.value.id == "pytest"
            )
        ):
            return True
    return False


def function_has_assertion(func_node) -> bool:
    """Public predicate: does ONE test function carry an assertion?

    Phase T.3 reuses this in the traceability gate — one implementation,
    two callers. Intraprocedural (documented limitation in the module
    docstring).
    """
    return _contains_assertion(func_node)


def analyze_source(source: str) -> list[str]:
    """Return the names of assert-free test functions in the source."""
    tree = ast.parse(source)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _is_test_function(node):
            continue
        if not _contains_assertion(node):
            offenders.append(node.name)
    return offenders


def count_assert_free_tests(roots: list[str]) -> list[str]:
    """Scan every test file (``test_*.py`` AND ``*_test.py`` — the latter
    form exists under tests/integration) under the roots; return offender
    names."""
    offenders: list[str] = []
    for root in roots:
        base = Path(root)
        for path in list(base.rglob("test_*.py")) + list(base.rglob("*_test.py")):
            parts = set(path.parts)
            if parts & _SKIP_DIRS:
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            try:
                names = analyze_source(source)
            except SyntaxError:
                continue
            for name in names:
                offenders.append(f"{path}:{name}")
    return offenders


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GATE-39 — zero-assertion test ratchet (assert-free test functions must not grow)."
    )
    parser.add_argument(
        "--roots",
        nargs="+",
        default=DEFAULT_ROOTS,
        help="directories scanned for test_*.py files (default: %(default)s)",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="baseline JSON path (default: scripts/zero_assertion_baseline.json)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="record the CURRENT count as the new floor (after a fix wave)",
    )
    args = parser.parse_args(argv)

    offenders = count_assert_free_tests(args.roots)
    count = len(offenders)

    if args.update:
        payload = {
            "count": count,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        args.baseline.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"GATE-39: baseline written — count={count}")
        return 0

    try:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        baseline_count = int(baseline["count"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"GATE-39: baseline missing or unreadable ({exc}) — run --update first")
        return 2

    if count > baseline_count:
        print(
            f"GATE-39: {count} assert-free test function(s) — growth over "
            f"baseline {baseline_count}. Every new test must carry at least "
            f"one real assertion (assert / self.assert* / pytest.raises / "
            f"mock assert_*); helper-based assertions count as assert-free "
            f"(documented intraprocedural limitation)."
        )
        for offender in offenders[:20]:
            print(f"  {offender}")
        if count > 20:
            print(f"  ... and {count - 20} more")
        return 1

    print(f"GATE-39: clean — {count} assert-free test function(s) (baseline {baseline_count})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
