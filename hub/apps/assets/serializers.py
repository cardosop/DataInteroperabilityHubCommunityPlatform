"""
Asset Serializers
"""
import re

from rest_framework import serializers
from .models import Asset, AssetStatus, AssetVisibility, DQStatus, ComplianceStatus

# Asset keys are user-facing tenant-scoped identifiers used in URLs, contract
# bindings, and ODPS payloads. They must be lowercase alphanumeric with optional
# single hyphens between segments — no underscores, uppercase, or punctuation —
# so the same value renders identically across UI, API, and downstream systems.
_ASSET_KEY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_asset_key(value: str) -> str:
    """Enforce the asset-key format (lowercase, digits, single hyphens)."""
    if not _ASSET_KEY_RE.match(value or ""):
        raise serializers.ValidationError(
            "Invalid key format: must be lowercase alphanumeric with hyphens "
            "between segments (e.g. 'my-asset-1'). Underscores, uppercase, and "
            "other punctuation are not allowed."
        )
    return value


class AssetSerializer(serializers.ModelSerializer):
    """Serializer for Asset model"""
    contract_id = serializers.SerializerMethodField()
    dataset_id = serializers.SerializerMethodField()

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
            'updated_at',
            'contract_id',
            'dataset_id',
        ]
        read_only_fields = [
            'id',
            'tenant',
            'version',
            'dq_status',
            'compliance_status',
            'created_by',
            'created_at',
            'updated_at',
            'contract_id',
            'dataset_id',
        ]

    def get_contract_id(self, obj):
        """Get the ID of the active contract for this asset"""
        try:
            active_contract = obj.contracts.filter(status="ACTIVE").first()
            if active_contract:
                return str(active_contract.id)
            # If no active contract, return the latest contract
            latest_contract = obj.contracts.order_by('-created_at').first()
            if latest_contract:
                return str(latest_contract.id)
        except Exception:
            pass
        return None

    def get_dataset_id(self, obj):
        """Get the ID of the latest dataset for this asset"""
        try:
            # Get latest dataset by version (or created_at if version not set)
            latest_dataset = obj.datasets.order_by('-version', '-created_at').first()
            if latest_dataset:
                return str(latest_dataset.id)
        except Exception:
            pass
        return None


class AssetCreateSerializer(serializers.Serializer):
    """Serializer for asset creation"""
    key = serializers.CharField(
        max_length=255,
        help_text="Human-friendly identifier, unique per tenant. Must be lowercase alphanumeric with hyphens.",
        validators=[validate_asset_key],
    )
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

    def save(self, instance=None):
        """
        Update the asset instance with validated data.

        Args:
            instance: Asset instance to update (uses self.instance if not provided)

        Returns:
            Updated Asset instance
        """
        # Use instance from constructor if not provided
        if not instance:
            instance = self.instance

        if not instance:
            raise ValueError("Instance is required for AssetUpdateSerializer.save()")

        # Update fields
        if 'name' in self.validated_data:
            instance.name = self.validated_data['name']
        if 'description' in self.validated_data:
            instance.description = self.validated_data['description']
        if 'domain' in self.validated_data:
            instance.domain = self.validated_data['domain']
        if 'status' in self.validated_data:
            instance.status = self.validated_data['status']
        if 'visibility' in self.validated_data:
            instance.visibility = self.validated_data['visibility']

        # Save and return
        instance.save()
        return instance


class DataFirstAssetCreateSerializer(serializers.Serializer):
    """Serializer for data-first asset creation (POST /api/v1/assets/data-first/)."""

    file_id = serializers.UUIDField(help_text="ID of the uploaded file")
    key = serializers.CharField(
        max_length=255,
        help_text="Asset key, unique per tenant. Must be lowercase alphanumeric with hyphens.",
        validators=[validate_asset_key],
    )
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    domain = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    visibility = serializers.ChoiceField(
        choices=AssetVisibility.choices, default=AssetVisibility.INTERNAL, required=False
    )


class AttachDatasetSerializer(serializers.Serializer):
    """Serializer for attaching dataset to asset"""
    dataset_id = serializers.UUIDField(help_text="ID of the dataset to attach")


class AttachContractSerializer(serializers.Serializer):
    """Serializer for attaching contract to asset"""
    contract_id = serializers.UUIDField(help_text="ID of the contract to attach")


class ExternalResourceSerializer(serializers.Serializer):
    """Serializer for external resource reference"""
    id = serializers.UUIDField(read_only=True)
    resource_id = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    url = serializers.URLField(read_only=True)
    format = serializers.CharField(read_only=True)
    size_bytes = serializers.IntegerField(read_only=True, allow_null=True)
    marketplace_type = serializers.CharField(read_only=True)
    metadata = serializers.DictField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    # Download status fields
    is_downloaded = serializers.BooleanField(read_only=True, help_text="Whether resource has been downloaded")
    file_id = serializers.UUIDField(read_only=True, allow_null=True, help_text="File ID if downloaded")
    dataset_id = serializers.UUIDField(read_only=True, allow_null=True, help_text="Dataset ID if downloaded")


class BatchDownloadSerializer(serializers.Serializer):
    """Serializer for batch download request"""
    resource_ids = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
        max_length=100,
        help_text="List of resource IDs to download (max 100)"
    )


class ResourceDownloadResponseSerializer(serializers.Serializer):
    """Serializer for resource download response"""
    resource_id = serializers.CharField()
    status = serializers.CharField(help_text="Download status: success, failed, skipped")
    file_id = serializers.UUIDField(allow_null=True, help_text="File ID if download succeeded")
    dataset_id = serializers.UUIDField(allow_null=True, help_text="Dataset ID if download succeeded")
    error = serializers.CharField(allow_null=True, allow_blank=True, help_text="Error message if download failed")
    message = serializers.CharField(allow_null=True, allow_blank=True, help_text="Status message")

