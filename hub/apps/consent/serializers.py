from __future__ import annotations

from rest_framework import serializers

from hub.apps.consent.models import ConsentPurpose, ConsentRecord


class ConsentPurposeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsentPurpose
        fields = [
            "id",
            "key",
            "name",
            "description",
            "retention_days",
            "is_active",
            "iab_purpose_id",
            "iab_special_feature_optins",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["tenant"] = self.context["tenant"]
        return super().create(validated_data)


class ConsentRecordSerializer(serializers.ModelSerializer):
    purpose_key = serializers.CharField(source="purpose.key", read_only=True)

    class Meta:
        model = ConsentRecord
        fields = [
            "id",
            "tenant",
            "user",
            "purpose",
            "purpose_key",
            "status",
            "granted_at",
            "revoked_at",
            "canonical_payload",
            "proof_hmac",
            "signing_key_index",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "user",
            "status",
            "granted_at",
            "revoked_at",
            "canonical_payload",
            "proof_hmac",
            "signing_key_index",
            "created_at",
            "updated_at",
            "purpose_key",
        ]


class ConsentRecordCreateSerializer(serializers.Serializer):
    purpose_id = serializers.UUIDField()
    payload = serializers.JSONField(required=False, default=dict)


class ConsentRecordUpdateSerializer(serializers.Serializer):
    """Re-grant with a new canonical payload (proof recomputed)."""

    payload = serializers.JSONField(required=False, default=dict)
