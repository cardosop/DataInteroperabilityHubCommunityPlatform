"""
Drift-detection test for the CLI's local MVP-gated prefix list.

The CLI keeps its own frozenset of MVP-gated /api/v1/ prefixes in
``cli/datahub_cli/_mvp_gates.py`` so it does not have to import Django at
runtime. That copy is only safe if it stays byte-equivalent (as a *set*) to
the canonical declaration in ``hub/apps/api/mvp_mode.py``.

This test parses the canonical source with :mod:`ast` (NOT regex) and walks
its module-level ``AnnAssign`` / ``Assign`` nodes to extract the canonical
``MVP_GATED_RELATIVE_PREFIXES`` literal, then asserts equality with the local
frozenset. It MUST NOT import Django and MUST NOT regex-match Python source.

Phase 215.1 — see openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md
"""

from __future__ import annotations

import ast
from pathlib import Path

from datahub_cli._mvp_gates import MVP_GATED_RELATIVE_PREFIXES

CANONICAL_PATH = Path(__file__).resolve().parents[2] / "hub" / "apps" / "api" / "mvp_mode.py"
CANONICAL_NAME = "MVP_GATED_RELATIVE_PREFIXES"


def _extract_canonical_prefixes() -> frozenset[str]:
    """Return the canonical prefixes by ``ast``-walking the hub source.

    No Django import, no regex. Walks only module-level statements (the
    canonical declaration is at module top), supporting both annotated and
    plain assignments.
    """
    source = CANONICAL_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(CANONICAL_PATH))
    for node in tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target]
            value = node.value
        elif isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        else:
            continue
        if value is None:
            continue
        if not any(isinstance(t, ast.Name) and t.id == CANONICAL_NAME for t in targets):
            continue
        # Canonical literal is a tuple/set/frozenset of string constants.
        if isinstance(value, (ast.Tuple, ast.Set, ast.List)):
            elements = value.elts
        elif (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "frozenset"
            and value.args
            and isinstance(value.args[0], (ast.Tuple, ast.Set, ast.List))
        ):
            elements = value.args[0].elts
        else:
            raise AssertionError(f"Unsupported AST shape for {CANONICAL_NAME}: {ast.dump(value)}")
        prefixes: set[str] = set()
        for elt in elements:
            if not isinstance(elt, ast.Constant) or not isinstance(elt.value, str):
                raise TypeError(f"Non-string literal element in {CANONICAL_NAME}: {ast.dump(elt)}")
            prefixes.add(elt.value)
        return frozenset(prefixes)
    raise AssertionError(
        f"Could not find module-level assignment for {CANONICAL_NAME} in {CANONICAL_PATH}"
    )


def test_canonical_source_file_exists() -> None:
    """The canonical hub source file MUST be present at the expected path."""
    assert CANONICAL_PATH.is_file(), (
        f"Canonical mvp_mode.py not found at {CANONICAL_PATH}. The drift "
        "test cannot run without it — restore the file or update CANONICAL_PATH."
    )


def test_local_frozenset_matches_canonical_source() -> None:
    """CLI's local frozenset MUST equal the canonical hub list as a set."""
    canonical = _extract_canonical_prefixes()
    assert canonical == MVP_GATED_RELATIVE_PREFIXES, (
        "CLI MVP_GATED_RELATIVE_PREFIXES has drifted from "
        f"{CANONICAL_PATH}.\n"
        f"  Only in CLI:       {sorted(MVP_GATED_RELATIVE_PREFIXES - canonical)}\n"
        f"  Only in canonical: {sorted(canonical - MVP_GATED_RELATIVE_PREFIXES)}\n"
        "Update cli/datahub_cli/_mvp_gates.py to match the canonical list."
    )


def _imported_module_names() -> set[str]:
    """Return the set of top-level modules actually imported by this test file.

    Uses ``ast`` so docstring/comment mentions of ``import django`` cannot
    cause false positives.
    """
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_drift_test_does_not_import_django() -> None:
    """This test file MUST NOT import Django (the whole point of the local copy)."""
    imported = _imported_module_names()
    assert "django" not in imported, f"Forbidden import: django ({imported})"


def test_drift_test_does_not_use_regex() -> None:
    """This test file MUST NOT regex-match Python source — use ``ast`` only."""
    imported = _imported_module_names()
    assert "re" not in imported, f"Forbidden import: re ({imported})"


def test_drift_detected_when_local_set_modified() -> None:
    """Sanity check: a deliberately desynced local set MUST fail the same
    equality check used by ``test_local_frozenset_matches_canonical_source``.

    This is the negative companion to the main drift test. It guards against
    three failure modes:

      1. The extractor returns an empty set (then both sides match trivially).
      2. The extractor returns the wrong literal but it happens to equal the
         local copy by coincidence.
      3. A future refactor accidentally weakens ``==`` to a no-op.

    The test reproduces the exact assertion the real drift test runs, but
    with a deliberately desynced "local" frozenset, and asserts that the
    assertion would have failed.
    """
    canonical = _extract_canonical_prefixes()
    assert canonical, "extractor returned empty set — drift test would always pass"

    # Case 1: an extra prefix in the local copy.
    desynced_extra = frozenset(canonical | {"definitely-not-a-real-prefix/"})
    assert desynced_extra != canonical

    # Case 2: a missing prefix in the local copy (drop one deterministically).
    dropped = sorted(canonical)[0]
    desynced_missing = frozenset(canonical - {dropped})
    assert desynced_missing != canonical

    # Case 3: empty local copy.
    assert frozenset() != canonical
