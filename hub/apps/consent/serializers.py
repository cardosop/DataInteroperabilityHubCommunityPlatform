from __future__ import annotations

from rest_framework import serializers

from hub.apps.consent.models import ConsentPurpose, ConsentRecord


class ConsentPurposeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsentPurpose
        fields = (
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
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def create(self, validated_data):
        validated_data["tenant"] = self.context["tenant"]
        return super().create(validated_data)

    def validate(self, attrs):
        """W4.3 (R2-I3/E5) — active-key uniqueness at the API boundary.

        The DB constraint ``consent_purpose_tenant_key_uniq`` is a
        partial unique index over ACTIVE rows only (re-creating a
        deactivated key is legitimate). Two edges must surface as clean
        400s instead of IntegrityError 500s:

        * creating a purpose whose key is held by another ACTIVE row
          (pre-fix: raw IntegrityError 500),
        * reactivating a deactivated row while a NEW active row holds
          the key — the edge the partial index itself introduces.
        """
        attrs = super().validate(attrs)
        tenant = self.context.get("tenant")
        instance = getattr(self, "instance", None)
        key = attrs.get("key") or (instance.key if instance else None)
        is_active = attrs.get("is_active", instance.is_active if instance else True)
        if tenant is not None and key is not None and is_active:
            qs = ConsentPurpose.objects.filter(tenant=tenant, key=key, is_active=True)
            if instance is not None:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"key": "An active consent purpose with this key already exists."}
                )
        return attrs


class ConsentRecordSerializer(serializers.ModelSerializer):
    purpose_key = serializers.CharField(source="purpose.key", read_only=True)

    class Meta:
        model = ConsentRecord
        fields = (
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
        )
        read_only_fields = (
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
        )


class ConsentRecordCreateSerializer(serializers.Serializer):
    purpose_id = serializers.UUIDField()
    payload = serializers.JSONField(required=False, default=dict)


class ConsentRecordUpdateSerializer(serializers.Serializer):
    """Re-grant with a new canonical payload (proof recomputed)."""

    payload = serializers.JSONField(required=False, default=dict)
