"""
Asset Serializers
"""
from rest_framework import serializers
from .models import Asset, AssetStatus, AssetVisibility, DQStatus, ComplianceStatus


class AssetSerializer(serializers.ModelSerializer):
    """Serializer for Asset model"""
    
    class Meta:
        model = Asset
        fields = [
            'id',
            'tenant',
            'key',
            'name',
            'description',
            'domain',
            'status',
            'visibility',
            'dq_status',
            'compliance_status',
            'version',
            'created_by',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'tenant',
            'version',
            'dq_status',
            'compliance_status',
            'created_by',
            'created_at',
            'updated_at'
        ]


class AssetCreateSerializer(serializers.Serializer):
    """Serializer for asset creation"""
    key = serializers.CharField(max_length=255, help_text="Human-friendly identifier, unique per tenant")
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    domain = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    visibility = serializers.ChoiceField(choices=AssetVisibility.choices, default=AssetVisibility.INTERNAL, required=False)


class AssetUpdateSerializer(serializers.Serializer):
    """Serializer for asset update"""
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    domain = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    status = serializers.ChoiceField(choices=AssetStatus.choices, required=False)
    visibility = serializers.ChoiceField(choices=AssetVisibility.choices, required=False)
    version = serializers.IntegerField(help_text="Current version for optimistic locking")


class AttachDatasetSerializer(serializers.Serializer):
    """Serializer for attaching dataset to asset"""
    dataset_id = serializers.UUIDField(help_text="ID of the dataset to attach")


class AttachContractSerializer(serializers.Serializer):
    """Serializer for attaching contract to asset"""
    contract_id = serializers.UUIDField(help_text="ID of the contract to attach")

