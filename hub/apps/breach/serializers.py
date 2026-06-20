from __future__ import annotations

from rest_framework import serializers

from hub.apps.breach.models import (
    BreachIncident,
    BreachIncidentStatus,
    BreachNotification,
    BreachTenantTemplateOverride,
)


class BreachNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BreachNotification
        fields = [
            "id",
            "incident",
            "regime",
            "supervisory_authority_id",
            "status",
            "channel",
            "statutory_due_at_utc",
            "rendered_subject",
            "rendered_body",
            "template_version",
            "delivery_proof_sha256",
            "proof_storage_path",
            "proof_s3_version_id",
            "object_lock_retention_days",
            "outbound_reference",
            "sent_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class BreachIncidentSerializer(serializers.ModelSerializer):
    notifications = BreachNotificationSerializer(many=True, read_only=True)

    class Meta:
        model = BreachIncident
        fields = [
            "id",
            "title",
            "summary",
            "regimes",
            "discovered_at",
            "status",
            "statutory_authority_deadline_utc",
            "legal_hold",
            "legal_hold_reason",
            "last_sla_level",
            "created_by",
            "details_json",
            "created_at",
            "updated_at",
            "notifications",
        ]
        read_only_fields = [
            "id",
            "status",
            "statutory_authority_deadline_utc",
            "last_sla_level",
            "created_by",
            "created_at",
            "updated_at",
            "notifications",
        ]


class BreachIncidentCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=512)
    summary = serializers.CharField(required=False, allow_blank=True, default="")
    regimes = serializers.ListField(child=serializers.CharField(), min_length=1)
    discovered_at = serializers.DateTimeField()


class BreachIncidentStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=BreachIncidentStatus.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class BreachMarkSentSerializer(serializers.Serializer):
    outbound_reference = serializers.CharField(max_length=512)


class BreachTenantTemplateOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = BreachTenantTemplateOverride
        fields = [
            "id",
            "tenant",
            "regime",
            "subject_template",
            "body_template",
            "template_version",
            "updated_by",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "template_version", "updated_by", "updated_at"]


class BreachTenantTemplateWriteSerializer(serializers.Serializer):
    regime = serializers.CharField(max_length=32)
    subject_template = serializers.CharField(required=False, allow_blank=True, default="")
    body_template = serializers.CharField(required=False, allow_blank=True, default="")
