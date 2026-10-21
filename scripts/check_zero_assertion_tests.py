#!/usr/bin/env python3
"""GATE-39 — zero-assertion test checker (Phase T.1 / W13, extended W12.10).

TWO dishonesty classes, each ratcheted (growth-only):

1. **assert-free tests** — a test function with NO assertion passes
   vacuously: the function under test can return None, raise, or
   regress, and the suite stays green.  The paid-tree vacuity audit
   (Phase P.9) fixed the known sites by hand; this gate pins the class
   with a ratcheted count.

2. **tautology sites (W12.10)** — an assertion that is TRUE BY
   CONSTRUCTION: ``assert True``, ``assert 1 == 1``,
   ``self.assertEqual(x, x)``, ``self.assertTrue("literal")``,
   ``self.assertIsNone(None)``, …  The site documents a check that
   never runs; it is the placeholder-class that masks missing logic
   (the named liar was ``cli/tests/unit/test_installation.py``
   ``assert True``).  Every site is counted; the baseline absorbs the
   one DELIBERATE site — the falsifiability probe's
   ``test_gate_probe.py`` sanity test, which the harness mutates to
   prove this gate flips RED (an injection grows the count).

What counts as an assertion (intraprocedural — see the limitation note):
``assert`` statements, ``self.assert*`` / ``self.fail*`` (unittest),
``pytest.raises`` / ``pytest.fail`` / ``pytest.warns``, and mock assertion
calls (``.assert_called*`` / ``.assert_not_called`` /
``.assert_has_calls``). Everything else — bare calls, side effects,
returns — leaves the function assert-free and counted.

Tautology detection is CONSERVATIVE (never a false PASS on the named
classes): a comparison whose operands are IDENTICAL pure expressions
(names/attributes/subscripts — no calls, because ``f() is f()`` is a
real memoization test) or LITERALS with equal values is flagged.
Always-failing assertions (``assert 1 == 2``) are NOT flagged — they
are broken tests, not silent passes.

LIMITATION (documented rather than mis-reported): the analysis is
INTRAPROCEDURAL — a test whose assertions live in a helper counts as
assert-free. This OVER-counts (the count is an upper bound on the true
number of vacuous tests), and the gate only fails on GROWTH, so the
limitation can only cause a false FAIL on a legitimate new
helper-asserting test, never a false PASS. The baseline therefore absorbs
the existing helper-asserting tests; converting one to inline assertions
only ever lowers the count.

Ratchet semantics (same shape as GATE-35): neither count may exceed the
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


# ── W12.10 — tautology detection ────────────────────────────────────────────


def _node_dump(node: ast.AST) -> str:
    return ast.dump(node, annotate_fields=False)


def _is_literal(node: ast.AST) -> bool:
    """A constant, or a constant-only container (evaluable via
    ast.literal_eval)."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_literal(elt) for elt in node.elts)
    return False


def _literal_value(node: ast.AST):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None


def _is_pure_expression(node: ast.AST) -> bool:
    """A call-free expression (Name/Attribute/Subscript chains).

    ``f() is f()`` is a REAL memoization test — calls are never
    flagged as identical operands."""
    return isinstance(node, (ast.Name, ast.Attribute, ast.Subscript))


def _operands_identical(
    left: ast.AST,
    right: ast.AST,
    *,
    allow_calls: bool = False,
) -> bool:
    """True when the two operands are the SAME expression or two
    literals with equal values.

    ``allow_calls`` admits identical CALL expressions (``f(x) == f(x)``
    is trivially equal for any deterministic function) — used for
    equality comparisons.  Identity comparisons keep calls out
    (``f() is f()`` is a REAL memoization test)."""
    if _is_literal(left) and _is_literal(right):
        lv, rv = _literal_value(left), _literal_value(right)
        return lv is not None and rv is not None and lv == rv
    if allow_calls:
        return _node_dump(left) == _node_dump(right)
    return (
        _is_pure_expression(left)
        and _is_pure_expression(right)
        and _node_dump(left) == _node_dump(right)
    )


def _truthiness(node: ast.AST) -> bool | None:
    """Truthiness of a literal (None when not a literal)."""
    if not _is_literal(node):
        return None
    value = _literal_value(node)
    return bool(value)


def tautology_reason(node: ast.AST) -> str | None:
    """Return a reason string when `node` (an ast.Assert or an
    assertion-shaped ast.Call) is TRUE BY CONSTRUCTION, else None.

    Covered classes: ``assert <truthy literal>``, ``assert a == b``
    with identical pure operands or equal literals, ``assert a is b``
    with identical pure operands, ``self.assertTrue(<truthy
    literal>)``, ``self.assertFalse(<falsy literal>)``,
    ``self.assertEqual(a, b)`` / ``assertIs(a, b)`` with identical
    pure operands or equal literals, ``assertIsNone(None)``,
    ``assertIsNotNone(<non-None literal>)``.
    """
    if isinstance(node, ast.Assert):
        return tautology_reason(node.test)

    reason: str | None = None

    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        op = node.ops[0]
        left, right = node.left, node.comparators[0]
        eq_identical = isinstance(op, ast.Eq) and _operands_identical(
            left, right, allow_calls=True
        )
        is_identical = isinstance(op, ast.Is) and _operands_identical(
            left, right
        )
        if eq_identical or is_identical:
            reason = "comparison of identical operands"
    elif isinstance(node, ast.Constant) and _truthiness(node):
        reason = "assert on a truthy literal"
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        name = node.func.attr
        args = node.args
        if name == "assertTrue" and args and _truthiness(args[0]):
            reason = "assertTrue on a truthy literal"
        elif name == "assertFalse" and args and _truthiness(args[0]) is False:
            reason = "assertFalse on a falsy literal"
        elif name in ("assertEqual", "assertEquals") and len(args) == 2:
            if _operands_identical(args[0], args[1], allow_calls=True):
                reason = f"{name} of identical operands"
        elif name == "assertIs" and len(args) == 2:
            if _operands_identical(args[0], args[1]):
                reason = "assertIs of identical operands"
        elif name == "assertIsNone" and args and _is_literal(args[0]):
            # literal None (falsy literal) — assertIsNone(None);
            # assertIsNone(result) is a REAL check.
            if _literal_value(args[0]) is None:
                reason = "assertIsNone of literal None"
        elif name == "assertIsNotNone" and args:
            value = _literal_value(args[0])
            if value is not None and _is_literal(args[0]):
                reason = "assertIsNotNone of a non-None literal"
    return reason


def find_tautology_sites(source: str) -> list[str]:
    """Return "test_fn:line:reason" for every tautological assertion
    site inside a test function."""
    tree = ast.parse(source)
    sites: list[str] = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _is_test_function(func):
            continue
        for child in ast.walk(func):
            if isinstance(child, ast.Assert):
                reason = tautology_reason(child.test)
                if reason:
                    sites.append(f"{func.name}:{child.lineno}:{reason}")
            elif isinstance(child, ast.Call):
                reason = tautology_reason(child)
                if reason:
                    sites.append(f"{func.name}:{child.lineno}:{reason}")
    return sites


def count_tautology_sites(roots: list[str]) -> list[str]:
    """Scan every test file under the roots; return "path:site" strings."""
    sites: list[str] = []
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
                found = find_tautology_sites(source)
            except SyntaxError:
                continue
            for site in found:
                sites.append(f"{path}:{site}")
    return sites


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
    tautology_sites = count_tautology_sites(args.roots)
    tautology_count = len(tautology_sites)

    if args.update:
        payload = {
            "count": count,
            "tautology_count": tautology_count,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        args.baseline.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(
            f"GATE-39: baseline written — count={count}, "
            f"tautology_count={tautology_count}"
        )
        return 0

    try:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        baseline_count = int(baseline["count"])
        baseline_tautology_count = int(baseline.get("tautology_count", 0))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"GATE-39: baseline missing or unreadable ({exc}) — run --update first")
        return 2

    failed = False
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
        failed = True

    if tautology_count > baseline_tautology_count:
        print(
            f"GATE-39: {tautology_count} tautological assertion site(s) — "
            f"growth over baseline {baseline_tautology_count}. An assertion "
            f"that is true by construction (assert True, assertEqual(x, x), "
            f"assertTrue('literal'), assertIsNone(None), …) documents a "
            f"check that never runs — replace it with the real check."
        )
        for site in tautology_sites[:20]:
            print(f"  {site}")
        if tautology_count > 20:
            print(f"  ... and {tautology_count - 20} more")
        failed = True

    if failed:
        return 1

    print(
        f"GATE-39: clean — {count} assert-free test function(s) "
        f"(baseline {baseline_count}); {tautology_count} tautology site(s) "
        f"(baseline {baseline_tautology_count})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
