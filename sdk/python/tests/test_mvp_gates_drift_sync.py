"""
Drift-detection test for the SDK's local MVP-gated prefix list.

Mirrors ``cli/tests/test_mvp_gates_drift_sync.py``: ``ast.parse``-walks the
canonical hub source and asserts equality with the SDK's local frozenset.
No regex, no Django import.

Phase 215.2 — see openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md
"""
from __future__ import annotations

import ast
from pathlib import Path

from datahub_interoperability._mvp_gates import MVP_GATED_PREFIXES


CANONICAL_PATH = (
    Path(__file__).resolve().parents[3] / "hub" / "apps" / "api" / "mvp_mode.py"
)
CANONICAL_NAME = "MVP_GATED_RELATIVE_PREFIXES"


def _extract_canonical_prefixes() -> frozenset[str]:
    """Return the canonical prefixes by ``ast``-walking the hub source."""
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
            raise AssertionError(
                f"Unsupported AST shape for {CANONICAL_NAME}: {ast.dump(value)}"
            )
        prefixes: set[str] = set()
        for elt in elements:
            if not isinstance(elt, ast.Constant) or not isinstance(elt.value, str):
                raise TypeError(
                    f"Non-string literal element in {CANONICAL_NAME}: {ast.dump(elt)}"
                )
            prefixes.add(elt.value)
        return frozenset(prefixes)
    raise AssertionError(
        f"Could not find module-level assignment for {CANONICAL_NAME} in {CANONICAL_PATH}"
    )


def _imported_module_names() -> set[str]:
    """Return the set of top-level modules imported by this test file (AST-based)."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_canonical_source_file_exists() -> None:
    """The canonical hub source file MUST be present at the expected path."""
    assert CANONICAL_PATH.is_file(), (
        f"Canonical mvp_mode.py not found at {CANONICAL_PATH}. "
        "Restore the file or update CANONICAL_PATH."
    )


def test_local_frozenset_matches_canonical_source() -> None:
    """SDK's local frozenset MUST equal the canonical hub list as a set."""
    canonical = _extract_canonical_prefixes()
    assert canonical == MVP_GATED_PREFIXES, (
        f"SDK MVP_GATED_PREFIXES has drifted from {CANONICAL_PATH}.\n"
        f"  Only in SDK:       {sorted(MVP_GATED_PREFIXES - canonical)}\n"
        f"  Only in canonical: {sorted(canonical - MVP_GATED_PREFIXES)}\n"
        "Update sdk/python/datahub_interoperability/_mvp_gates.py to match."
    )


def test_drift_test_does_not_import_django() -> None:
    """This test file MUST NOT import Django (the whole point of the local copy)."""
    imported = _imported_module_names()
    assert "django" not in imported, f"Forbidden import: django ({imported})"


def test_drift_test_does_not_use_regex() -> None:
    """This test file MUST NOT regex-match Python source — use ``ast`` only."""
    imported = _imported_module_names()
    assert "re" not in imported, f"Forbidden import: re ({imported})"


def test_drift_detected_when_local_set_modified() -> None:
    """Negative companion: prove the equality check would fail under desync."""
    canonical = _extract_canonical_prefixes()
    assert canonical, "extractor returned empty set — drift test would always pass"
    assert frozenset(canonical | {"definitely-not-a-real-prefix/"}) != canonical
    dropped = sorted(canonical)[0]
    assert frozenset(canonical - {dropped}) != canonical
    assert frozenset() != canonical
