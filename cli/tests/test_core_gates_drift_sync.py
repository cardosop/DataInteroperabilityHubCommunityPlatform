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
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "_PAID_MODULES"
        ) or (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and getattr(node.targets[0], "id", None) == "_PAID_MODULES"
        ):
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
        "marketplace",
        "baas",
        "ml",
        "billing",
        "social",
        "semantic",
        "graphql",
        "developer",
    }
    expected = manifest_groups & known_cli_groups
    assert expected == PAID_CLI_GROUPS, (
        f"CLI paid-group list drifted from the manifest: {PAID_CLI_GROUPS} != {expected}"
    )


def test_detect_core_gated_feature():
    from datahub_cli._core_gates import detect_core_gated_feature

    hit = detect_core_gated_feature("https://hub.example.com/api/v1/marketplace/listings/")
    assert hit is not None
    assert hit[0] == "marketplace"
    assert "SaaS feature" in hit[1]
    assert detect_core_gated_feature("https://hub.example.com/api/v1/assets/") is None
    assert detect_core_gated_feature("/api/v1/developer/plugins/") is None  # core group


def test_detect_core_gated_feature_reachability():
    """P.5 D3 — gating resolves by paid-path PREFIX, not by first URL
    segment.  Nested paid paths hosted under a CORE app's prefix
    (``integrations/marketplace/…`` — the integrations app is core, but
    its marketplace views are paid functionality) MUST be gated; a
    core-owned sibling under the same app MUST NOT be."""
    from datahub_cli._core_gates import detect_core_gated_feature

    # The exact path-shape mismatch the old first-segment matcher missed:
    hit = detect_core_gated_feature(
        "https://hub.example.com/api/v1/integrations/marketplace/connections/"
    )
    assert hit is not None, "nested paid path must be gated"
    assert hit[0] == "marketplace", f"expected group marketplace, got {hit[0]!r}"
    assert "SaaS feature" in hit[1]

    # Core sibling under the same core app prefix stays reachable:
    assert detect_core_gated_feature("/api/v1/integrations/health/") is None

    # Every canonical paid prefix is gated:
    for prefix in (
        "api/v1/billing/",
        "api/v1/baas/",
        "api/v1/ml/",
        "api/v1/ai/",
        "api/v1/semantic/",
        "api/v1/social/",
        "api/v1/admin/connect/review-queue/",
        "graphql/",
        "graphql-graphene/",
    ):
        assert detect_core_gated_feature(f"https://hub.example.com/{prefix}x") is not None, (
            f"paid prefix {prefix!r} is not gated"
        )

    # Prefix matcher must not over-gate on shared first segments:
    assert detect_core_gated_feature("/api/v1/semanticx/") is None


def test_paid_url_prefixes_match_manifest():
    """The CLI's paid-path table must be byte-identical (as a set) to the
    canonical ``hub.apps.manifest.PAID_URL_PREFIXES`` — the single source
    of truth for both the backend registry consumers and the CLI gate."""
    from datahub_cli._core_gates import PAID_URL_PREFIXES

    source = MANIFEST_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MANIFEST_PATH))
    manifest_prefixes = None
    for node in tree.body:
        value = None
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "PAID_URL_PREFIXES"
        ) or (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and getattr(node.targets[0], "id", None) == "PAID_URL_PREFIXES"
        ):
            value = node.value
        if value is None:
            continue
        if isinstance(value, ast.Call) and getattr(value.func, "id", None) == "frozenset":
            inner = value.args[0]
            if isinstance(inner, ast.Set):
                manifest_prefixes = frozenset(
                    e.value for e in inner.elts if isinstance(e, ast.Constant)
                )
                break
    assert manifest_prefixes is not None, "PAID_URL_PREFIXES not found in manifest"
    assert manifest_prefixes == PAID_URL_PREFIXES, (
        f"CLI paid-prefix table drifted from the manifest: {PAID_URL_PREFIXES ^ manifest_prefixes}"
    )
