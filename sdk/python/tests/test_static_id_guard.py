"""
Phase 216.X.2 — static-id lint guard for SDK tests.

Mirror of ``cli/tests/test_static_id_guard.py``. AST-walks every Python
test module under ``sdk/python/tests/`` and fails on string literals
matching ``(asset|contract|tenant|webhook|user)[_-]<rest>``. The fix is
``fresh_id(prefix)`` from ``sdk/python/tests/fixtures/test_data.py``.
Use ``# noqa: PHASE216-STATIC-ID`` to exempt a single line.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


SDK_TESTS_DIR = Path(__file__).resolve().parent
FORBIDDEN_RE = re.compile(
    r"^(asset|contract|tenant|webhook|user)[_-][A-Za-z0-9_-]+$"
)

# Pre-Phase-216 backlog. Filled by the first guard run; new entries
# only added for legacy files written before this rule existed.
ALLOWLIST: frozenset[str] = frozenset({
    "test_all_apis_odps_integration.py",
    "test_baas_api.py",
    "test_contracts_api.py",
    "test_integration.py",
    "test_mesh_compliance_api.py",
    "test_mesh_policies_api.py",
    "test_mesh_topology_api.py",
    "test_ml_api_e2e.py",
    "test_odcs_export_integration.py",
    "test_odcs_export.py",
    "test_phase118b_endpoint_fixes.py",
    "test_phase26_sdk_integration.py",
    "test_python_js_odps_consistency.py",
})


def _string_literals(tree: ast.Module) -> list[tuple[int, str]]:
    docstring_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstring_nodes.add(id(body[0].value))
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstring_nodes:
                continue
            out.append((node.lineno, node.value))
    return out


def _scan_file(path: Path) -> list[tuple[int, str]]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    findings: list[tuple[int, str]] = []
    src_lines = src.splitlines()
    for lineno, value in _string_literals(tree):
        if FORBIDDEN_RE.match(value):
            line = src_lines[lineno - 1] if 0 <= lineno - 1 < len(src_lines) else ""
            if "PHASE216-STATIC-ID" in line:
                continue
            findings.append((lineno, value))
    return findings


def _python_test_files() -> list[Path]:
    return sorted(p for p in SDK_TESTS_DIR.rglob("test_*.py") if p.is_file())


@pytest.mark.parametrize(
    "path",
    _python_test_files(),
    ids=lambda p: str(p.relative_to(SDK_TESTS_DIR)),
)
def test_no_forbidden_static_id_literal(path: Path) -> None:
    rel = str(path.relative_to(SDK_TESTS_DIR))
    findings = _scan_file(path)
    if rel in ALLOWLIST:
        if not findings:
            pytest.fail(
                f"{rel} is in PHASE216 ALLOWLIST but has no forbidden "
                "static-ids — remove it from ALLOWLIST to lock the win."
            )
        return
    if findings:
        message = (
            f"{rel} contains forbidden static test-id literal(s) "
            f"matching ``(asset|contract|tenant|webhook|user)[_-]…``. "
            "Use ``fresh_id(prefix)`` from "
            "``sdk/python/tests/fixtures/test_data.py`` instead, or "
            "annotate the line with ``# noqa: PHASE216-STATIC-ID``.\n"
        )
        for lineno, value in findings:
            message += f"  {rel}:{lineno}: {value!r}\n"
        pytest.fail(message)
