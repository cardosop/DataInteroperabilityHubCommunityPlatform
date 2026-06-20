#!/usr/bin/env python3
"""Produce an accurate baseline of E2E hidden-failure metrics for Meshant.

Output is a single JSON document describing:

* pytest: swallowed exceptions, ORM queries, status-code assertions, test skips
* playwright: `test.skip(true, ...)`, `page.on('pageerror', ...)`, `page.request.*`, `verifyViaApi(...)`

Python metrics are computed by the stdlib `ast` module in-process.
TypeScript metrics are computed by a Node helper (`e2e_metrics_typescript.cjs`)
which uses `@typescript-eslint/parser` already installed under frontend/node_modules.

CLI:
    python scripts/e2e_metrics.py \\
        --pytest-dir tests/e2e \\
        --playwright-dir frontend/e2e \\
        --output e2e-metrics.json
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
TS_HELPER = SCRIPT_DIR / "e2e_metrics_typescript.cjs"

PY_METRIC_KEYS = (
    "except_exception_pass",
    "orm_query",
    "status_code_assertion",
    "test_skip_call",
)

TS_METRIC_KEYS = (
    "test_skip_true",
    "page_on_pageerror",
    "page_request_call",
    "verify_via_api_call",
)

ORM_METHODS = {
    "get",
    "filter",
    "all",
    "create",
    "update_or_create",
    "get_or_create",
    "exists",
    "count",
    "first",
    "last",
    "bulk_create",
    "bulk_update",
    "none",
}


# ------------------------------------------------------------------ Python AST


def _is_except_exception_pass(handler: ast.ExceptHandler) -> bool:
    """True when the handler catches bare or `Exception` AND body is a single `pass`."""
    # body == [Pass()] — exactly one statement, a bare pass
    if len(handler.body) != 1 or not isinstance(handler.body[0], ast.Pass):
        return False
    # type is None → bare `except:` OR type is `Exception`
    t = handler.type
    if t is None:
        return True
    if isinstance(t, ast.Name) and t.id == "Exception":
        return True
    return False


def _is_orm_call(node: ast.AST) -> bool:
    """True when node is `SomeModel.objects.<ORM_METHOD>(...)`."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr not in ORM_METHODS:
        return False
    # func.value should be `<Model>.objects` (Attribute)
    inner = func.value
    if not isinstance(inner, ast.Attribute) or inner.attr != "objects":
        return False
    # and inner.value must be a capitalised identifier (class-like)
    if isinstance(inner.value, ast.Name) and inner.value.id[:1].isupper():
        return True
    return False


def _references_status_code(expr: ast.AST) -> bool:
    """Recursively check if `expr` contains an Attribute access `.status_code`."""
    for sub in ast.walk(expr):
        if isinstance(sub, ast.Attribute) and sub.attr == "status_code":
            return True
    return False


def _is_unittest_assert_method(attr: str) -> bool:
    """True for unittest.TestCase assertion methods that take a value as an arg."""
    return attr in {
        "assertEqual",
        "assertNotEqual",
        "assertIn",
        "assertNotIn",
        "assertGreater",
        "assertGreaterEqual",
        "assertLess",
        "assertLessEqual",
        "assertTrue",
        "assertFalse",
        "assertIs",
        "assertIsNot",
    }


def _is_status_code_assertion(node: ast.AST) -> bool:
    """True when node asserts on an HTTP response status code.

    Covers two common idioms:

    1. Plain pytest/assert style:  assert resp.status_code == 201
    2. unittest TestCase style:    self.assertEqual(resp.status_code, 201)

    For (1) we require the left operand to be a `.status_code` Attribute and
    at least one comparator to be an integer constant. For (2) we require at
    least one positional argument to reference `.status_code` and the method
    to be a known unittest assertion.
    """
    # Form 1: assert expr
    if isinstance(node, ast.Assert):
        test = node.test
        if not isinstance(test, ast.Compare):
            return False
        left = test.left
        if not (isinstance(left, ast.Attribute) and left.attr == "status_code"):
            return False
        return any(
            isinstance(c, ast.Constant) and isinstance(c.value, int) for c in test.comparators
        )

    # Form 2: self.assertEqual(resp.status_code, 201)
    if isinstance(node, ast.Call):
        func = node.func
        if not (isinstance(func, ast.Attribute) and _is_unittest_assert_method(func.attr)):
            return False
        # any positional or keyword argument that references .status_code qualifies
        for arg in node.args:
            if _references_status_code(arg):
                return True
        for kw in node.keywords:
            if kw.value is not None and _references_status_code(kw.value):
                return True
    return False


def _is_test_skip_call(node: ast.AST) -> bool:
    """True when node is `pytest.skip(...)` or `self.skipTest(...)`."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        if func.attr == "skip" and isinstance(func.value, ast.Name) and func.value.id == "pytest":
            return True
        if func.attr == "skipTest" and isinstance(func.value, ast.Name) and func.value.id == "self":
            return True
    return False


def count_python_metrics(path: Path) -> dict[str, int]:
    """Return {metric_key: count} for a single .py file.

    Raises `SyntaxError` if the file does not parse. That is intentional — a
    metrics script that silently drops unparseable files is the exact problem
    we are trying to solve.
    """
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))

    counts = dict.fromkeys(PY_METRIC_KEYS, 0)
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and _is_except_exception_pass(node):
            counts["except_exception_pass"] += 1
        elif _is_orm_call(node):
            counts["orm_query"] += 1
        elif _is_status_code_assertion(node):
            counts["status_code_assertion"] += 1
        elif _is_test_skip_call(node):
            counts["test_skip_call"] += 1
    return counts


# ------------------------------------------------------------- TypeScript (Node helper)


def count_typescript_metrics(paths: list[Path]) -> dict[str, dict[str, int]]:
    """Return {abs_path: {metric_key: count}} by invoking the Node helper once.

    Batches all paths in a single Node process to amortise startup cost (parser
    load is ~150ms; per-file counting is fast).
    """
    if not paths:
        return {}
    argv = ["node", str(TS_HELPER), *[str(p) for p in paths]]
    result = subprocess.run(argv, check=False, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        # Surface the real error to the caller — silent failure here is exactly
        # the anti-pattern this metrics work exists to kill.
        raise RuntimeError(
            f"TypeScript metric helper failed (exit {result.returncode}).\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )
    data = json.loads(result.stdout)
    # helper uses the path strings as given; normalise back to strings for the caller
    return {str(k): v for k, v in data.items()}


# ------------------------------------------------------------------- Aggregation


def _discover(root: Path, suffixes: Iterable[str]) -> list[Path]:
    """Depth-first glob for files under `root` matching any of the suffixes."""
    if not root.exists():
        return []
    out: list[Path] = []
    for suffix in suffixes:
        out.extend(sorted(root.rglob(f"*{suffix}")))
    return out


def _relpath(p: str | Path) -> str:
    """Return `p` as a forward-slash path relative to REPO_ROOT when possible.

    Diffs across developer machines and CI runners share the same repo layout
    but different absolute prefixes; normalising keeps the artifact portable.
    """
    path = Path(p).resolve()
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        # Outside the repo (fixtures in a tmpdir, etc.) — keep absolute.
        return path.as_posix()


def aggregate_metrics(
    *,
    python_files: list[Path],
    typescript_files: list[Path],
) -> dict:
    """Run both counters and assemble the top-level JSON structure.

    Files with zero count for a given metric are omitted from the by_file map.
    This keeps the artifact small and diff-friendly on PR comments. Paths in
    the output are relative to REPO_ROOT when possible (see _relpath).
    """
    py_totals: defaultdict[str, int] = defaultdict(int)
    py_by_file: dict[str, dict[str, int]] = defaultdict(dict)
    for p in python_files:
        counts = count_python_metrics(p)
        for k, v in counts.items():
            py_totals[k] += v
            if v:
                py_by_file.setdefault(_relpath(p), {})[k] = v

    ts_raw = count_typescript_metrics(typescript_files) if typescript_files else {}
    ts_by_file: dict[str, dict[str, int]] = {_relpath(k): v for k, v in ts_raw.items()}
    ts_totals: defaultdict[str, int] = defaultdict(int)
    for counts in ts_by_file.values():
        for k, v in counts.items():
            ts_totals[k] += v

    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "pytest": {
            "files_scanned": len(python_files),
            "except_exception_pass_count": py_totals["except_exception_pass"],
            "orm_query_count": py_totals["orm_query"],
            "status_code_assertion_count": py_totals["status_code_assertion"],
            "test_skip_call_count": py_totals["test_skip_call"],
            "except_exception_pass_by_file": {
                f: m["except_exception_pass"]
                for f, m in py_by_file.items()
                if m.get("except_exception_pass")
            },
        },
        "playwright": {
            "files_scanned": len(typescript_files),
            "test_skip_true_count": ts_totals["test_skip_true"],
            "page_on_pageerror_count": ts_totals["page_on_pageerror"],
            "page_request_call_count": ts_totals["page_request_call"],
            "verify_via_api_call_count": ts_totals["verify_via_api_call"],
            "test_skip_true_by_file": {
                f: c["test_skip_true"] for f, c in ts_by_file.items() if c.get("test_skip_true")
            },
        },
    }
    return result


# ------------------------------------------------------------------------- CLI


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Produce a JSON baseline of E2E hidden-failure metrics."
    )
    parser.add_argument(
        "--pytest-dir",
        type=Path,
        default=REPO_ROOT / "tests" / "e2e",
        help="Directory scanned for .py files.",
    )
    parser.add_argument(
        "--playwright-dir",
        type=Path,
        default=REPO_ROOT / "frontend" / "e2e",
        help="Directory scanned for .ts/.tsx files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON to this path (default: stdout).",
    )
    parser.add_argument(
        "--skip-typescript",
        action="store_true",
        help="Skip TypeScript counting (useful if node is unavailable).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    py_files = _discover(args.pytest_dir, (".py",))
    ts_files = [] if args.skip_typescript else _discover(args.playwright_dir, (".ts", ".tsx"))

    result = aggregate_metrics(python_files=py_files, typescript_files=ts_files)
    payload = json.dumps(result, indent=2, sort_keys=True)

    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        sys.stdout.write(payload + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
