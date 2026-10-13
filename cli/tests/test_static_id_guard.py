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
    r"^(asset|contract|tenant|webhook|user"
    r"|Asset|Contract|Tenant|Webhook|User"
    r")[_-][A-Za-z0-9_-]+$"
)

# The pattern above also matches *schema vocabulary* — ``asset_id`` as a
# payload key, ``asset_ids`` as a kwarg, ``asset-id`` as the CLI option
# name quoted in an expected error message, ``asset_count`` as a response
# field.  None of those name a backend resource, so none can collide
# under xdist; flagging them trained readers to ignore the guard.
#
# A literal whose final ``[_-]``-separated segment is one of these words
# is a field/option name.  A real static id ends in an opaque token
# instead — ``asset-1``, ``contract_abc``, ``tenant_test`` are all still
# caught, because ``1`` / ``abc`` / ``test`` are not schema words.
SCHEMA_TAIL_WORDS: frozenset[str] = frozenset(
    {
        "id",
        "ids",
        "key",
        "keys",
        "name",
        "names",
        "count",
        "type",
        "types",
        "status",
        "slug",
        "ref",
        "refs",
        "uri",
        "url",
        "path",
        "list",
        "at",
        "by",
    }
)


def _is_schema_name(value: str) -> bool:
    """True if ``value`` reads as a field/option name, not a resource id."""
    tail = re.split(r"[_-]", value)[-1]
    return tail.lower() in SCHEMA_TAIL_WORDS


# Files allowed to retain pre-Phase-216 static ids while the migration
# proceeds. Each entry is a backlog item to be cleared in a follow-up.
# A test file MUST NOT be added to this list as part of new work — only
# legacy files written before Phase 216 are eligible.
ALLOWLIST: frozenset[str] = frozenset(
    {
        # Pre-Phase-216 backlog. Each entry is a file written before the
        # static-id rule existed; clearing one entry = one PR that migrates
        # that file's static literals to ``fresh_id``. New tests MUST NOT
        # be added here.
        "integration/test_cli_assets_odps.py",
        "integration/test_installation_config_auth.py",
        "integration/test_odps_error_scenarios.py",
        "unit/test_commands_assets.py",
        "unit/test_commands_compliance.py",
        "unit/test_commands_contracts.py",
        "unit/test_commands_lineage.py",
        "unit/test_commands_marketplace_sync.py",
        "unit/test_commands_mesh_domains.py",
        "unit/test_commands_mesh_policies.py",
        "unit/test_commands_mesh_topology.py",
        "unit/test_config.py",
        "unit/test_configuration.py",
        "unit/test_odps_errors.py",
        "unit/test_output_formatting.py",
        "unit/test_phase118a_endpoint_param_fixes.py",
    }
)


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

    # A string in dict-key position names a payload field, never a
    # resource — ``{"asset_id": asset_id}`` must flag the value, not the
    # key.
    dict_key_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    dict_key_nodes.add(id(key))

    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstring_nodes or id(node) in dict_key_nodes:
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
        if FORBIDDEN_RE.match(value) and not _is_schema_name(value):
            line = src_lines[lineno - 1] if 0 <= lineno - 1 < len(src_lines) else ""
            if "PHASE216-STATIC-ID" in line:
                continue
            findings.append((lineno, value))
    return findings


def _python_test_files() -> list[Path]:
    """Return every ``test_*.py`` under ``cli/tests/`` (recursive)."""
    return sorted(p for p in CLI_TESTS_DIR.rglob("test_*.py") if p.is_file())


@pytest.mark.parametrize(
    "literal",
    [
        "asset-1",  # noqa: PHASE216-STATIC-ID — guard test vector
        "contract_abc",  # noqa: PHASE216-STATIC-ID — guard test vector
        "tenant_test",  # noqa: PHASE216-STATIC-ID — guard test vector
        "asset-fixture-1",  # noqa: PHASE216-STATIC-ID — guard test vector
        "user-42",  # noqa: PHASE216-STATIC-ID — guard test vector
        "webhook-a",  # noqa: PHASE216-STATIC-ID — guard test vector
    ],
)
def test_guard_flags_real_static_ids(literal: str) -> None:
    """A literal ending in an opaque token is a static id and MUST flag."""
    assert FORBIDDEN_RE.match(literal) is not None
    assert not _is_schema_name(literal)


@pytest.mark.parametrize(
    "literal",
    [
        "asset_id",
        "contract_id",
        "asset_ids",
        "asset_count",
        "asset-id",
        "tenant_slug",
        "user_name",
        "asset_status",
        "webhook_url",
        "contract_type",
    ],
)
def test_guard_ignores_schema_names(literal: str) -> None:
    """Field/option names name no resource and MUST NOT flag."""
    assert _is_schema_name(literal)


def test_guard_ignores_dict_keys_but_flags_values() -> None:
    """``{"asset_id": "asset-1"}`` must flag the value, never the key."""
    tree = ast.parse('payload = {"asset_id": "asset-1"}')
    values = [v for _, v in _string_literals(tree)]
    assert "asset_id" not in values, "dict key was not excluded"
    assert "asset-1" in values, "dict value was wrongly excluded"  # noqa: PHASE216-STATIC-ID


def test_allowlist_has_no_stale_entries() -> None:
    """Every ALLOWLIST entry MUST reference an existing test file.

    When a test file is deleted or renamed its ALLOWLIST entry must be
    removed at the same time.  Stale entries mask missing coverage by
    silently ignoring files that no longer exist.
    """
    existing = {str(p.relative_to(CLI_TESTS_DIR)) for p in _python_test_files()}
    stale = sorted(ALLOWLIST - existing)
    if stale:
        message = (
            f"ALLOWLIST contains {len(stale)} stale entr{'y' if len(stale) == 1 else 'ies'} "
            f"that reference non-existent test file(s).  "
            "Remove the stale entries from ALLOWLIST in "
            "cli/tests/test_static_id_guard.py:\n"
        )
        for entry in stale:
            message += f"  {entry}\n"
        pytest.fail(message)


@pytest.mark.parametrize(
    "path", _python_test_files(), ids=lambda p: str(p.relative_to(CLI_TESTS_DIR))
)
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
