"""
Phase 228.F3.6 — Serializers for the Lineage Subscription endpoints.

Two thin serializers backing the
``/api/v1/lineage/subscriptions/`` ViewSet:

* :class:`LineageSubscriptionSerializer` — full read/write shape.
* :class:`LineageSubscriptionPatchSerializer` — accepts only the
  fields a user is allowed to edit after creation
  (``severity_threshold``, ``in_app``, ``email`` — Slack is a
  v2 follow-on per REQ-LIN-F3-008).

Note: tenant-scoped read-permission validation is the **viewset's**
job (it has the ``request`` user and the queryset gates).  These
serializers are concerned with field shape + rich validation
errors only.
"""

from __future__ import annotations

from rest_framework import serializers

from hub.apps.contracts.models import (
    LineageSubscription,
    LineageSubscriptionSeverity,
)


class LineageSubscriptionSerializer(serializers.ModelSerializer):
    """REQ-LIN-F3-002 / F3-003 read+create shape."""

    class Meta:
        model = LineageSubscription
        fields = (
            "id",
            "user",
            "source_contract",
            "source_asset",
            "severity_threshold",
            "in_app",
            "email",
            "slack",
            "created_at",
            "last_dispatched_at",
        )
        read_only_fields = ("id", "user", "created_at", "last_dispatched_at")

    def validate(self, attrs):
        # Enforce the XOR invariant at the API layer too — the DB
        # CHECK constraint is the safety net but we want to return
        # a typed 400 instead of the IntegrityError.
        source_contract = attrs.get("source_contract")
        source_asset = attrs.get("source_asset")
        both_set = source_contract is not None and source_asset is not None
        neither_set = source_contract is None and source_asset is None
        if both_set or neither_set:
            raise serializers.ValidationError(
                {
                    "code": "INVALID_SUBSCRIPTION_SOURCE",
                    "detail": ("Exactly one of source_contract or source_asset must be set."),
                },
            )
        # Severity must be one of the canonical tiers.  ModelSerializer
        # already validates the choices field, but we double-check so
        # the error code is uniform with the DB layer.
        threshold = attrs.get("severity_threshold")
        if threshold and threshold not in LineageSubscriptionSeverity.values:
            raise serializers.ValidationError(
                {
                    "code": "INVALID_SEVERITY_THRESHOLD",
                    "detail": f"Unknown severity tier: {threshold}.",
                },
            )
        return attrs


class LineageSubscriptionPatchSerializer(serializers.ModelSerializer):
    """REQ-LIN-F3-003 PATCH — only the channel + threshold are mutable.

    The source FK is immutable post-create (a user who wants to
    re-target deletes + re-creates).  This keeps the dispatcher's
    debounce key stable across edits.
    """

    class Meta:
        model = LineageSubscription
        fields = (
            "severity_threshold",
            "in_app",
            "email",
            "slack",
        )
