"""
Phase 228.F2 (REQ-LIN-F2-002 / F2.7) — patch-payload serializers
for the field-level lineage editor.

* :class:`LineageEdgeInputSerializer` — one edge in the desired
  state.  All fields except ``edge_type`` are user-supplied; the
  service-layer composes the resulting :class:`LineageEdge` rows
  from these dicts.

* :class:`LineageEditPatchSerializer` — the top-level patch shape.
  Carries the desired ``edges`` list (the FULL post-patch state,
  not just the diff — a "set the lineage to this list" semantic).

The PATCH endpoint diffs the current open edges against the
serializer's output, closes removed edges, opens new ones (F2.8),
and re-serialises ``hub_contract_json.lineage`` from the resulting
list.

Why a full-state patch (not RFC-6902)
-------------------------------------
The frontend editor (F2.17) is a two-pane table where the user
adds/removes/edits rows then clicks Save.  The diff lives in the
client; the server takes the resulting list and reconciles.  An
RFC-6902 ``[{op:'add', ...}, {op:'remove', ...}]`` would force the
client to compute the diff before send — fragile when the user
opens two editor tabs and one tab's view goes stale.  Full-state
PATCH + ETag (REQ-LIN-F2-002) is the simpler concurrency model.
"""

from __future__ import annotations

from rest_framework import serializers


class LineageEdgeInputSerializer(serializers.Serializer):
    """One edge in the desired post-patch state."""

    source_contract = serializers.UUIDField(allow_null=True, required=False)
    target_contract = serializers.UUIDField(allow_null=True, required=False)
    source_model = serializers.CharField(
        max_length=255,
        allow_blank=True,
        required=False,
        default="",
    )
    source_field = serializers.CharField(
        max_length=255,
        allow_blank=True,
        required=False,
        default="",
    )
    target_model = serializers.CharField(
        max_length=255,
        allow_blank=True,
        required=False,
        default="",
    )
    target_field = serializers.CharField(
        max_length=255,
        allow_blank=True,
        required=False,
        default="",
    )
    edge_type = serializers.ChoiceField(
        choices=[
            "upload",
            "transformation",
            "derivation",
            "export",
            "reference",
        ],
        default="reference",
    )
    transformation_ref = serializers.CharField(
        max_length=512,
        allow_blank=True,
        required=False,
        default="",
    )
    job_ref = serializers.CharField(
        max_length=512,
        allow_blank=True,
        required=False,
        default="",
    )

    def validate(self, attrs):
        # An edge SHALL have at least one (source_contract, target_contract).
        # An edge with both NULL has no anchoring contract — it can't
        # be reconciled to a HubContract row at apply time.
        if not (attrs.get("source_contract") or attrs.get("target_contract")):
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Edge must specify at least source_contract or target_contract"
                    ],
                    "code": "INVALID_EDGE_ENDPOINTS",
                }
            )
        return attrs


# Per-request edge cap (REQ-LIN-F2-002 — "Cap 1000 edges; 413 over").
# Enforced on the FULL post-patch list, not the diff: a 5000-edge
# legacy contract can have its lineage edited if the patch keeps
# ≤1000 of them.
F2_MAX_EDGES_PER_PATCH = 1000


class LineageEditPatchSerializer(serializers.Serializer):
    """Top-level lineage-edit patch."""

    edges = LineageEdgeInputSerializer(many=True)

    def validate_edges(self, value: list[dict]) -> list[dict]:
        if len(value) > F2_MAX_EDGES_PER_PATCH:
            # The view layer turns ValidationError(code=...) into a
            # 413; default DRF behaviour returns 400.  We surface a
            # ``code`` the view recognises.
            raise serializers.ValidationError(
                {
                    "detail": (
                        f"Lineage patch must contain at most "
                        f"{F2_MAX_EDGES_PER_PATCH} edges; "
                        f"got {len(value)}"
                    ),
                    "code": "PAYLOAD_TOO_LARGE",
                }
            )
        return value


__all__ = [
    "F2_MAX_EDGES_PER_PATCH",
    "LineageEdgeInputSerializer",
    "LineageEditPatchSerializer",
]
