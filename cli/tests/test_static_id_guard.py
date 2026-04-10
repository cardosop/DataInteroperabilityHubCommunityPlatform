"""
Phase 216.X.2 — static-id lint guard.

The spec requires that every test which creates a named backend resource
use the ``fresh_id(prefix)`` fixture from
``cli/tests/fixtures/test_data.py``. Static literals like
``"asset-1"`` / ``"contract_abc"`` / ``"tenant_test"`` cause cross-test
collisions when xdist runs in parallel and are forbidden in tests under
``cli/tests/``.

This file is a *meta-test*: it ast-walks every Python module under
``cli/tests/`` and fails if it finds a string literal whose contents
match the forbidden pattern. AST-based (not regex over source) so
docstrings and comments are excluded automatically.

The check is opt-in per-test via a tail comment:

    asset_id = "asset-fixture-1"  # noqa: PHASE216-STATIC-ID

Files that pre-date Phase 216.X.2 are recorded in ``ALLOWLIST`` so the
guard can be enabled incrementally — every entry there represents a
backlog item, not an exemption from the rule.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


CLI_TESTS_DIR = Path(__file__).resolve().parent
FORBIDDEN_RE = re.compile(
    r"^(asset|contract|tenant|webhook|user)[_-][A-Za-z0-9_-]+$"
)

# Files allowed to retain pre-Phase-216 static ids while the migration
# proceeds. Each entry is a backlog item to be cleared in a follow-up.
# A test file MUST NOT be added to this list as part of new work — only
# legacy files written before Phase 216 are eligible.
ALLOWLIST: frozenset[str] = frozenset({
    # Pre-Phase-216 backlog. Each entry is a file written before the
    # static-id rule existed; clearing one entry = one PR that migrates
    # that file's static literals to ``fresh_id``. New tests MUST NOT
    # be added here.
    "e2e/test_asset_management_use_cases.py",
    "e2e/test_compliance_use_cases.py",
    "e2e/test_contract_management_use_cases.py",
    "e2e/test_data_quality_use_cases.py",
    "e2e/test_marketplace_sync_workflows.py",
    "e2e/test_ml_training_workflows.py",
    "integration/test_cli_assets_odps.py",
    "integration/test_cli_marketplace_odps.py",
    "integration/test_cli_odps_comprehensive.py",
    "integration/test_commands_real_api.py",
    "integration/test_installation_config_auth.py",
    "integration/test_ml_serving_cli_comprehensive.py",
    "integration/test_ml_training_commands_real_api.py",
    "integration/test_odh_cli_comprehensive_validation.py",
    "integration/test_odps_cli_workflows.py",
    "integration/test_odps_error_scenarios.py",
    "integration/test_payment_gateways_real_api.py",
    "integration/test_phase26_cli_integration.py",
    "integration/test_product_strategy_real_api.py",
    "unit/test_commands_assets.py",
    "unit/test_commands_baas.py",
    "unit/test_commands_compliance.py",
    "unit/test_commands_contracts.py",
    "unit/test_commands_lineage.py",
    "unit/test_commands_marketplace_sync.py",
    "unit/test_commands_mesh_domains.py",
    "unit/test_commands_mesh_policies.py",
    "unit/test_commands_mesh_topology.py",
    "unit/test_config.py",
    "unit/test_configuration.py",
    "unit/test_error_handling.py",
    "unit/test_odps_errors.py",
    "unit/test_output_formatting.py",
    "unit/test_phase118a_endpoint_param_fixes.py",
})


def _string_literals(tree: ast.Module) -> list[tuple[int, str]]:
    """Yield ``(lineno, value)`` for every string Constant in ``tree``.

    Excludes docstrings (the first statement of a module/class/function
    body) so README-style prose does not trip the guard.
    """
    docstring_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
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
    """Return forbidden ``(lineno, value)`` matches in ``path``."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    findings: list[tuple[int, str]] = []
    # Per-line noqa annotations exempt a single line.
    src_lines = src.splitlines()
    for lineno, value in _string_literals(tree):
        if FORBIDDEN_RE.match(value):
            line = src_lines[lineno - 1] if 0 <= lineno - 1 < len(src_lines) else ""
            if "PHASE216-STATIC-ID" in line:
                continue
            findings.append((lineno, value))
    return findings


def _python_test_files() -> list[Path]:
    """Return every ``test_*.py`` under ``cli/tests/`` (recursive)."""
    return sorted(p for p in CLI_TESTS_DIR.rglob("test_*.py") if p.is_file())


@pytest.mark.parametrize("path", _python_test_files(), ids=lambda p: str(p.relative_to(CLI_TESTS_DIR)))
def test_no_forbidden_static_id_literal(path: Path) -> None:
    """Each test file MUST NOT contain a forbidden static-id literal."""
    rel = str(path.relative_to(CLI_TESTS_DIR))
    findings = _scan_file(path)
    if rel in ALLOWLIST:
        # Allowlisted file — record but do not fail. We assert the
        # allowlist is current by failing if there are NO findings (so
        # an entry can be removed once the file is cleaned up).
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
            "``cli/tests/fixtures/test_data.py`` instead, or annotate "
            "the line with ``# noqa: PHASE216-STATIC-ID`` if it is a "
            "regex / docstring example.\n"
        )
        for lineno, value in findings:
            message += f"  {rel}:{lineno}: {value!r}\n"
        pytest.fail(message)
