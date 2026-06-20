from __future__ import annotations

from rest_framework import serializers

from hub.apps.dsar.models import (
    DSARRequest,
    DSARRequestType,
    DSARVerificationMethod,
)


class DSARRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = DSARRequest
        read_only_fields = (
            "id",
            "status",
            "public_reference_token",
            "created_at",
            "updated_at",
            "statutory_ack_deadline_utc",
            "statutory_fulfil_deadline_utc",
            "last_sla_level",
            "response_object_key",
            "response_manifest_sha256",
            "download_consumed_at",
            "download_url_issued_at",
        )
        fields = (
            "id",
            "request_type",
            "status",
            "regimes",
            "subject_email",
            "subject_name",
            "subject_timezone",
            "regulator_timezone",
            "linked_user",
            "verification_method",
            "extension_path_selected",
            "legal_hold",
            "legal_hold_reason",
            "public_reference_token",
            "statutory_ack_deadline_utc",
            "statutory_fulfil_deadline_utc",
            "last_sla_level",
            "response_object_key",
            "response_manifest_sha256",
            "download_consumed_at",
            "download_url_issued_at",
            "handler_notes",
            "created_at",
            "updated_at",
        )


class PublicDsarSubmitSerializer(serializers.Serializer):
    tenant_id = serializers.UUIDField()
    request_type = serializers.ChoiceField(choices=DSARRequestType.choices)
    subject_email = serializers.EmailField()
    subject_name = serializers.CharField(required=False, allow_blank=True, default="")
    subject_timezone = serializers.CharField(required=False, default="UTC")
    regulator_timezone = serializers.CharField(required=False, default="UTC")
    regimes = serializers.ListField(child=serializers.CharField(), min_length=1)
    hcaptcha_response = serializers.CharField()
    extension_path_selected = serializers.BooleanField(required=False, default=False)
    verification_method = serializers.ChoiceField(
        choices=DSARVerificationMethod.choices,
        required=False,
        default=DSARVerificationMethod.EMAIL_OTP,
    )


class PublicDsarOtpSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)
