"""
Phase 228.F1 (REQ-LIN-F1-001 / F1-004) — Lineage graph serializers.

Two serializers enforce the **load-bearing security boundary** between
the pre-purchase ``summary`` tier and the post-purchase ``full`` tier:

* :class:`LineageGraphSummarySerializer` — exposes node id/type/label
  and link source/target/edge_type ONLY.  The fields
  ``transformation_ref``, ``job_ref``, ``created_by_run``,
  ``source_field``, ``target_field`` are EXCLUDED via an explicit
  field allowlist.  A copy-paste edit that adds them is caught by
  ``test_listing_lineage_view.py::test_summary_excludes_forbidden_keys``.

* :class:`LineageGraphFullSerializer` — exposes the full edge metadata
  (transformation IP).  Only callers holding an ACTIVE
  :class:`Entitlement` reach this tier (enforced upstream by
  :func:`require_entitlement_or_summary`).

Why two distinct serializers (vs ``fields = include_full and EXTRA or BASE``)
----------------------------------------------------------------------------
A single serializer with conditional fields tends to drift: a future
edit might forget the `if include_full:` guard, leaking a forbidden
key.  Two classes make the distinction structural — the summary class
**physically does not have** the forbidden fields, so any drift
fails compile/import time, not at request time.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

# ---------------------------------------------------------------------------
# Forbidden-key set — pinned by the regression guard in
# ``test_listing_lineage_view.py::test_summary_excludes_forbidden_keys``.
# Keep this in lock-step with REQ-LIN-F1-001's exclusion list.
# ---------------------------------------------------------------------------

SUMMARY_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "transformation_ref",
        "job_ref",
        "created_by_run",
        "source_field",
        "target_field",
    }
)


# ---------------------------------------------------------------------------
# Summary tier — pre-purchase
# ---------------------------------------------------------------------------


class _SummaryNodeSerializer(serializers.Serializer):
    """A graph node in summary form.

    Carries identity + type + display label.  No transformation IP.
    """

    id = serializers.CharField()
    type = serializers.CharField(
        help_text="Node type (contract / asset / external / dataset).",
    )
    label = serializers.CharField(
        allow_blank=True,
        help_text="Display label — derived from contract/asset name; never from transformation_ref.",
    )


class _SummaryLinkSerializer(serializers.Serializer):
    """A graph link in summary form.

    Edge type is exposed so consumers can tell "transformation" from
    "reference" at a high level — but no transformation reference,
    no job reference, no field-level mapping.
    """

    source = serializers.CharField()
    target = serializers.CharField()
    edge_type = serializers.CharField(
        help_text="One of LineageEdgeType.choices — exposes the kind of relationship without revealing how.",
    )


class LineageGraphSummarySerializer(serializers.Serializer):
    """Pre-purchase lineage graph.  Strips transformation IP."""

    nodes = _SummaryNodeSerializer(many=True)
    links = _SummaryLinkSerializer(many=True)
    truncated = serializers.BooleanField(
        default=False,
        help_text="True when the result was clamped to the per-query row caps (REQ-LIN-F1-005 D2 mitigation).",
    )
    detail = serializers.CharField(default="summary", read_only=True)


# ---------------------------------------------------------------------------
# Full tier — post-purchase (entitlement required)
# ---------------------------------------------------------------------------


class _FullNodeSerializer(serializers.Serializer):
    id = serializers.CharField()
    type = serializers.CharField()
    label = serializers.CharField(allow_blank=True)


class _FullLinkSerializer(serializers.Serializer):
    source = serializers.CharField()
    target = serializers.CharField()
    edge_type = serializers.CharField()
    # The "transformation IP" surface — only exposed at the full tier.
    transformation_ref = serializers.CharField(allow_blank=True, default="")
    job_ref = serializers.CharField(allow_blank=True, default="")
    created_by_run = serializers.CharField(allow_blank=True, default="")
    source_field = serializers.CharField(allow_blank=True, default="")
    target_field = serializers.CharField(allow_blank=True, default="")


class LineageGraphFullSerializer(serializers.Serializer):
    """Post-purchase lineage graph.  Includes transformation IP."""

    nodes = _FullNodeSerializer(many=True)
    links = _FullLinkSerializer(many=True)
    truncated = serializers.BooleanField(default=False)
    detail = serializers.CharField(default="full", read_only=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def assert_no_forbidden_keys(payload: dict[str, Any]) -> None:
    """Defensive runtime check — raises ``ValueError`` if a summary
    payload accidentally carries any forbidden key.  The test suite
    pins the same invariant statically; this helper is the runtime
    second-line if a future serializer refactor leaks a key.

    Used by ``LineageService`` only when the test environment env
    var ``LINEAGE_SUMMARY_RUNTIME_GUARD=1`` is set — production
    treats the static serializer field allowlist as authoritative
    and skips the per-request walk for performance.
    """
    nodes: list[dict[str, Any]] = payload.get("nodes", []) or []
    links: list[dict[str, Any]] = payload.get("links", []) or []
    for link in links:
        bad = SUMMARY_FORBIDDEN_KEYS & set(link.keys())
        if bad:
            raise ValueError(
                f"Phase 228.F1 (REQ-LIN-F1-001) summary tier leaked forbidden "
                f"keys {sorted(bad)} on a link entry — this is the load-"
                f"bearing IP-leak boundary; the serializer allowlist must "
                f"be the only source of fields."
            )
    for node in nodes:
        bad = SUMMARY_FORBIDDEN_KEYS & set(node.keys())
        if bad:
            raise ValueError(
                f"Phase 228.F1 summary tier leaked forbidden keys {sorted(bad)} on a node entry."
            )


__all__ = [
    "SUMMARY_FORBIDDEN_KEYS",
    "LineageGraphFullSerializer",
    "LineageGraphSummarySerializer",
    "assert_no_forbidden_keys",
]
