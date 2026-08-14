"""
Governance Serializers

Serializers for governance models (AccessRequest, RetentionPolicy, ComplianceReport).
"""

from rest_framework import serializers

from .access_certification import AccessCertification
from .models import (
    AccessRequest,
    AccessRequestComment,
    ComplianceReport,
    RetentionPolicy,
)


# Phase 313.1 — the "order" field exists only when the marketplace app is
# installed (conditional FK on AccessRequest); the field lists adapt so the
# OpenAPI schema generation works in core-only mode.
from django.conf import settings

_ACCESS_REQUEST_ORDER_FIELDS = ["order"] if not settings.HUB_CORE_ONLY else []


class AccessRequestSerializer(serializers.ModelSerializer):
    """Serializer for AccessRequest"""

    class Meta:
        model = AccessRequest
        fields = [
            "id",
            "tenant",
            "requested_by",
            "asset",
            "dataset",
            "file",
            "reason",
            "requested_access_type",
            "status",
            "requires_approval",
            "approval_workflow",
            "current_approval_step",
            "approvers",
            "approved_by",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "expires_at",
            "access_granted_at",
            *(_ACCESS_REQUEST_ORDER_FIELDS),
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "requested_by",
            "created_at",
            "updated_at",
            "approved_by",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "access_granted_at",
            *_ACCESS_REQUEST_ORDER_FIELDS,
        ]


class AccessCertificationSerializer(serializers.ModelSerializer):
    """Serializer for AccessCertification"""

    class Meta:
        model = AccessCertification
        fields = [
            "id",
            "tenant",
            "user",
            "asset",
            "dataset",
            "certification_type",
            "status",
            "reviewer",
            "review_notes",
            "expires_at",
            "certified_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "certified_at",
            "created_at",
            "updated_at",
        ]


class RetentionPolicySerializer(serializers.ModelSerializer):
    """Serializer for RetentionPolicy"""

    regulation_keys = serializers.ListField(
        child=serializers.CharField(max_length=64, allow_blank=False),
        required=False,
        allow_empty=True,
    )

    def validate_regulation_keys(self, value):
        if value is None:
            return []
        out: list[str] = []
        for item in value:
            s = str(item).strip().upper()
            if not s:
                raise serializers.ValidationError("regulation_keys entries must be non-empty.")
            out.append(s)
        return sorted(set(out))

    def validate_retention_period_days(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("retention_period_days must be >= 0.")
        return value

    def validate_grace_period_days(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("grace_period_days must be >= 0.")
        return value

    class Meta:
        model = RetentionPolicy
        fields = [
            "id",
            "tenant",
            "name",
            "description",
            "asset",
            "dataset",
            "file",
            "policy_type",
            "retention_period_days",
            "event_trigger",
            "action",
            "grace_period_days",
            "legal_hold",
            "legal_hold_reason",
            "legal_hold_expires_at",
            "regulation_keys",
            "tombstoned_at",
            "hard_delete_scheduled_at",
            "enabled",
            "last_enforced_at",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "created_by",
            "created_at",
            "updated_at",
            "last_enforced_at",
            "tombstoned_at",
            "hard_delete_scheduled_at",
        ]


class RetentionLegalHoldUpdateSerializer(serializers.Serializer):
    """Privileged legal-hold patch payload (Phase 232.7)."""

    legal_hold = serializers.BooleanField()
    legal_hold_reason = serializers.CharField(required=False, allow_blank=True, default="")
    legal_hold_expires_at = serializers.DateTimeField(required=False, allow_null=True)


class ComplianceReportSerializer(serializers.ModelSerializer):
    """Serializer for ComplianceReport"""

    class Meta:
        model = ComplianceReport
        fields = [
            "id",
            "tenant",
            "regulation",
            "report_type",
            "report_data",
            "start_date",
            "end_date",
            "scheduled",
            "schedule_frequency",
            "email_recipients",
            "email_sent",
            "email_sent_at",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "created_by",
            "created_at",
            "updated_at",
            "email_sent",
            "email_sent_at",
        ]


class AccessRequestCommentSerializer(serializers.ModelSerializer):
    """Phase 272.1 — serializer for AccessRequestComment."""

    author_email = serializers.SerializerMethodField()

    class Meta:
        model = AccessRequestComment
        fields = [
            "id",
            "access_request",
            "author",
            "author_email",
            "body",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "author",
            "author_email",
            "created_at",
            "updated_at",
        ]

    def get_author_email(self, obj):
        if obj.author:
            return obj.author.email
        return None
