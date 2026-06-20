"""Serializers for processor registry (Phase 232.6)."""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from hub.apps.processor_agreements.models import (
    AssetProcessorMembership,
    Processor,
    ProcessorAgreement,
    ProcessorAgreementType,
)
from hub.apps.processor_agreements.validators import (
    validate_document_hash_hex,
    validate_document_uri_for_agreement,
)


class ProcessorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Processor
        fields = [
            "id",
            "tenant",
            "name",
            "legal_name",
            "country_code",
            "website",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]

    def create(self, validated_data):
        obj = Processor(**validated_data)
        obj.full_clean()
        obj.save()
        return obj

    def update(self, instance, validated_data):
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.full_clean()
        instance.save()
        return instance


class ProcessorAgreementSerializer(serializers.ModelSerializer):
    agreement_type = serializers.ChoiceField(choices=ProcessorAgreementType.choices)
    processor_name = serializers.CharField(source="processor.name", read_only=True)

    def validate_processor(self, proc: Processor) -> Processor:
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        if tenant and proc.tenant.pk != tenant.pk:
            raise serializers.ValidationError("Processor is not in the active tenant.")
        return proc

    class Meta:
        model = ProcessorAgreement
        fields = [
            "id",
            "tenant",
            "processor",
            "processor_name",
            "agreement_type",
            "document_uri",
            "document_hash",
            "effective_from",
            "expires_on",
            "sub_processors_declared",
            "jurisdiction_region",
            "registration_reference",
            "transfer_mechanism_summary",
            "status",
            "expiry_warn_windows_sent",
            "details_json",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "status",
            "expiry_warn_windows_sent",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate_document_hash(self, value: str) -> str:
        return validate_document_hash_hex(value)

    def validate_document_uri(self, value: str) -> str:
        try:
            return validate_document_uri_for_agreement(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def create(self, validated_data):
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        user = getattr(request, "user", None) if request else None
        obj = ProcessorAgreement(
            **validated_data,
            tenant=tenant,
            created_by=user if user and user.is_authenticated else None,
        )
        obj.full_clean()
        obj.save()
        return obj

    def update(self, instance, validated_data):
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.full_clean()
        instance.save()
        return instance


class AssetProcessorLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetProcessorMembership
        fields = ["id", "tenant", "asset", "processor", "created_at"]
        read_only_fields = ["id", "tenant", "created_at"]

    def validate(self, data):
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        asset = data["asset"]
        proc = data["processor"]
        if asset.tenant_id != proc.tenant_id:
            raise serializers.ValidationError("Asset and processor must belong to the same tenant.")
        if tenant and asset.tenant_id != tenant.id:
            raise serializers.ValidationError("Asset is not in the active tenant.")
        return data

    def create(self, validated_data):
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None
        link = AssetProcessorMembership(**validated_data, tenant=tenant)
        link.full_clean()
        link.save()
        return link
