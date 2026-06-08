"""Serializers for DPIA API."""

from __future__ import annotations
from rest_framework import serializers

from hub.apps.dpia.models import Dpia, DpiaStatus, ResidualRiskLevel
from hub.apps.tenants.request_tenant import get_request_tenant_id


class DpiaSerializer(serializers.ModelSerializer):
    def validate_asset(self, value):
        if value is None:
            return None
        request = self.context.get("request")
        if not request:
            return value
        tid = get_request_tenant_id(request)
        if not tid:
            raise serializers.ValidationError("Tenant context required to link an asset.")
        if str(value.tenant_id) != str(tid):
            raise serializers.ValidationError("Asset does not belong to your active tenant.")
        return value

    def validate_derived_from(self, value):
        if value is None:
            return None
        request = self.context.get("request")
        if not request:
            return value
        tid = get_request_tenant_id(request)
        if tid and str(value.tenant_id) != str(tid):
            raise serializers.ValidationError("Parent DPIA must belong to your active tenant.")
        return value

    class Meta:
        model = Dpia
        fields = [
            "id",
            "tenant",
            "asset",
            "title",
            "regime",
            "status",
            "version",
            "previous_version",
            "derived_from",
            "wizard_payload",
            "risk_residual",
            "next_review_due_at",
            "created_by",
            "reviewed_by",
            "reviewed_at",
            "dpo_summary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "status",
            "version",
            "previous_version",
            "next_review_due_at",
            "reviewed_by",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]


class DpiaReviewSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(
        choices=[
            DpiaStatus.APPROVED,
            DpiaStatus.REJECTED,
            DpiaStatus.REQUIRES_CONSULTATION,
        ]
    )
    risk_residual = serializers.ChoiceField(choices=[c[0] for c in ResidualRiskLevel.choices], required=False, allow_blank=True)
    dpo_summary = serializers.CharField(required=False, allow_blank=True, default="")


class DpiaConsultSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
