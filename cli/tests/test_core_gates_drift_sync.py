"""Drift-detection test for the CLI's paid-group list (Phase 313.4).

The CLI keeps its own frozenset of paid command groups in
``cli/datahub_cli/_core_gates.py`` so it does not import Django at runtime.
That copy is only safe if it matches the canonical manifest membership
(``hub/apps/manifest.py::_PAID_MODULES``), intersected with the groups the
CLI actually registers. This test parses the manifest with :mod:`ast` (NOT
regex) and must NOT import Django.
"""

from __future__ import annotations

import ast
from pathlib import Path

from datahub_cli._core_gates import PAID_CLI_GROUPS

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "hub" / "apps" / "manifest.py"


def _extract_manifest_paid_groups() -> frozenset[str]:
    """AST-walk the manifest for _PAID_MODULES; return last path segments."""
    source = MANIFEST_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MANIFEST_PATH))
    for node in tree.body:
        value = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "_PAID_MODULES":
                value = node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            if getattr(node.targets[0], "id", None) == "_PAID_MODULES":
                value = node.value
        if value is None:
            continue
        # frozenset({...}) — a Call wrapping a literal Set.
        if isinstance(value, ast.Call) and getattr(value.func, "id", None) == "frozenset":
            inner = value.args[0]
            if isinstance(inner, ast.Set):
                modules = [
                    e.value
                    for e in inner.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)
                ]
                return frozenset(m.split(".")[-1] for m in modules)
    raise AssertionError("_PAID_MODULES not found in manifest")


def test_paid_cli_groups_match_manifest():
    manifest_groups = _extract_manifest_paid_groups()
    # The CLI only lists groups that exist as registered commands; the
    # contract is: every PAID_CLI_GROUPS member comes from the manifest,
    # and every manifest-paid group that HAS a CLI group is listed.
    # (graphql_graphene / graphql_ld / rate_limiting / ai have no CLI group.)
    known_cli_groups = {
        "marketplace", "baas", "ml", "billing", "social", "semantic", "graphql", "developer",
    }
    expected = manifest_groups & known_cli_groups
    assert PAID_CLI_GROUPS == expected, (
        f"CLI paid-group list drifted from the manifest: {PAID_CLI_GROUPS} != {expected}"
    )


def test_detect_core_gated_feature():
    from datahub_cli._core_gates import detect_core_gated_feature

    hit = detect_core_gated_feature("https://hub.example.com/api/v1/marketplace/listings/")
    assert hit is not None and hit[0] == "marketplace"
    assert "SaaS feature" in hit[1]
    assert detect_core_gated_feature("https://hub.example.com/api/v1/assets/") is None
    assert detect_core_gated_feature("/api/v1/developer/plugins/") is None  # core group
