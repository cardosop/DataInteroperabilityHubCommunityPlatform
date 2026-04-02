"""
Marketplace Integration Serializers

REST API serializers for marketplace connection management.
"""
from rest_framework import serializers
from django.utils import timezone

from .models import MarketplaceConnection, MarketplaceSyncJob, MarketplaceMapping
from .base import MarketplaceType, SyncDirection, SyncStatus


class MarketplaceConnectionSerializer(serializers.ModelSerializer):
    """
    Serializer for MarketplaceConnection model (read operations).

    Security: The ``config`` field is **never** exposed in read responses.
    It contains encrypted credentials (API keys, connection strings, tokens).
    The field is omitted from Meta.fields (positive allowlist) and also
    listed in Meta.extra_kwargs as write_only for defense-in-depth.
    """

    marketplace_type_display = serializers.CharField(
        source='get_marketplace_type_display',
        read_only=True,
        help_text="Human-readable marketplace type"
    )
    tenant_name = serializers.CharField(
        source='tenant.name',
        read_only=True,
        help_text="Tenant name"
    )
    tenant = serializers.UUIDField(
        source='tenant.id',
        read_only=True,
        help_text="Tenant ID"
    )

    class Meta:
        model = MarketplaceConnection
        fields = [
            'id',
            'tenant',
            'tenant_name',
            'marketplace_type',
            'marketplace_type_display',
            'name',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'tenant',
            'tenant_name',
            'marketplace_type_display',
            'created_at',
            'updated_at',
        ]
        # Phase 90.4 — defense-in-depth: even though config is not in
        # ``fields``, mark it write_only so DRF will never serialize it
        # if the allowlist is accidentally widened in the future.
        extra_kwargs = {
            'config': {'write_only': True},
        }


class MarketplaceConnectionCreateSerializer(serializers.Serializer):
    """
    Serializer for creating a marketplace connection.

    Validates marketplace type, name uniqueness, and config structure.
    """
    marketplace_type = serializers.ChoiceField(
        choices=[(mt.value, mt.name.replace("_", " ").title()) for mt in MarketplaceType],
        help_text="Type of marketplace (e.g., SNOWFLAKE_DATA_MARKETPLACE, AWS_DATA_EXCHANGE)"
    )
    name = serializers.CharField(
        max_length=255,
        allow_blank=True,
        help_text="Human-readable name (empty/whitespace rejected by service layer)"
    )
    config = serializers.JSONField(
        write_only=True,
        help_text="Connection configuration dictionary (API keys, endpoints, etc.). Will be encrypted at rest."
    )
    is_active = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Whether this connection is active and can be used"
    )

    def validate_name(self, value):
        """Reject empty and whitespace-only names at serializer level."""
        if value is not None and isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise serializers.ValidationError("Connection name cannot be empty")
            return stripped
        return value

    def validate_config(self, value):
        """Validate config is a dictionary with size limit (Phase 92 DoS prevention)."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Configuration must be a JSON object (dictionary)")
        # Reject overly-large payloads (DoS prevention)
        import json
        json_str = json.dumps(value)
        if len(json_str) > 65536:  # 64KB limit
            raise serializers.ValidationError("Configuration too large (max 64KB)")
        return value

    def validate_marketplace_type(self, value):
        """Validate marketplace type is a valid enum value"""
        valid_types = [mt.value for mt in MarketplaceType]
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid marketplace type. Must be one of: {', '.join(valid_types)}"
            )
        return value

    def validate(self, attrs):
        """Cross-field validation"""
        # Config validation is already done in validate_config
        # Additional cross-field validations can be added here if needed
        return attrs


class MarketplaceConnectionUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating a marketplace connection.

    All fields are optional - only provided fields will be updated.
    """
    name = serializers.CharField(
        max_length=255,
        required=False,
        help_text="Human-readable name for this connection"
    )
    config = serializers.JSONField(
        required=False,
        write_only=True,
        help_text="Connection configuration dictionary. Will be encrypted at rest."
    )
    is_active = serializers.BooleanField(
        required=False,
        help_text="Whether this connection is active and can be used"
    )

    def validate_name(self, value):
        """Validate connection name if provided"""
        if value is not None:
            if not value.strip():
                raise serializers.ValidationError("Connection name cannot be empty")
            if len(value.strip()) < 1:
                raise serializers.ValidationError("Connection name must be at least 1 character")
            if len(value.strip()) > 255:
                raise serializers.ValidationError("Connection name cannot exceed 255 characters")
            return value.strip()
        return value

    def validate_config(self, value):
        """Validate config is a dictionary if provided"""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Configuration must be a JSON object (dictionary)")
        return value

    def validate(self, attrs):
        """Cross-field validation"""
        # Ensure at least one field is provided for update
        if not attrs:
            raise serializers.ValidationError("At least one field must be provided for update")
        return attrs

    def update(self, instance, validated_data):
        """Update marketplace connection with validated data."""
        for attr, value in validated_data.items():
            if attr == "config":
                instance.set_config(value)
            else:
                setattr(instance, attr, value)
        instance.save()
        return instance


class MarketplaceConnectionTestResponseSerializer(serializers.Serializer):
    """
    Serializer for connection test response.
    """
    success = serializers.BooleanField(
        help_text="Whether the connection test was successful"
    )
    message = serializers.CharField(
        help_text="Test result message"
    )
    error = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Error message if test failed"
    )
    tested_at = serializers.DateTimeField(
        help_text="Timestamp when the test was performed (ISO format)"
    )
    connection_id = serializers.UUIDField(
        help_text="ID of the tested connection"
    )


class MarketplaceSyncJobSerializer(serializers.ModelSerializer):
    """
    Serializer for MarketplaceSyncJob model (read operations).
    """
    tenant = serializers.UUIDField(
        source='tenant.id',
        read_only=True,
        help_text="Tenant ID"
    )
    tenant_name = serializers.CharField(
        source='tenant.name',
        read_only=True,
        help_text="Tenant name"
    )
    connection_id = serializers.UUIDField(
        source='connection.id',
        read_only=True,
        help_text="Connection ID"
    )
    connection_name = serializers.CharField(
        source='connection.name',
        read_only=True,
        help_text="Connection name"
    )
    direction_display = serializers.CharField(
        source='get_direction_display',
        read_only=True,
        help_text="Human-readable sync direction"
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True,
        help_text="Human-readable sync status"
    )

    class Meta:
        model = MarketplaceSyncJob
        fields = [
            'id',
            'tenant',
            'tenant_name',
            'connection_id',
            'connection_name',
            'direction',
            'direction_display',
            'status',
            'status_display',
            'items_synced',
            'items_failed',
            'errors',
            'metadata',
            'created_at',
            'updated_at',
            'completed_at',
        ]
        read_only_fields = [
            'id',
            'tenant',
            'tenant_name',
            'connection_id',
            'connection_name',
            'direction_display',
            'status_display',
            'items_synced',
            'items_failed',
            'errors',
            'metadata',
            'created_at',
            'updated_at',
            'completed_at',
        ]


class MarketplaceSyncRequestSerializer(serializers.Serializer):
    """
    Serializer for creating a marketplace sync job request.

    Supports both PUSH (sync assets to marketplace) and PULL (sync from marketplace) operations.
    """
    connection_id = serializers.UUIDField(
        help_text="ID of the marketplace connection to use for sync"
    )
    direction = serializers.ChoiceField(
        choices=[(sd.value, sd.name.replace("_", " ").title()) for sd in SyncDirection],
        help_text="Sync direction: PUSH (Hub → Marketplace) or PULL (Marketplace → Hub)"
    )
    # For PUSH direction
    asset_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        help_text="List of Hub asset IDs to synchronize (required for PUSH direction)"
    )
    # For PULL direction
    listing_ids = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False,
        allow_empty=True,
        help_text="List of marketplace listing IDs to sync (optional for PULL direction)"
    )
    filters = serializers.JSONField(
        required=False,
        allow_null=True,
        help_text="Optional dictionary of filters to apply (for PULL direction)"
    )
    options = serializers.JSONField(
        required=False,
        allow_null=True,
        help_text="Optional dictionary of sync options (e.g., dry_run, force_update, create_assets)"
    )

    def validate_direction(self, value):
        """Validate sync direction is a valid enum value"""
        valid_directions = [sd.value for sd in SyncDirection]
        if value not in valid_directions:
            raise serializers.ValidationError(
                f"Invalid sync direction. Must be one of: {', '.join(valid_directions)}"
            )
        return value

    def validate_asset_ids(self, value):
        """Validate asset_ids if provided"""
        if value is not None:
            if not isinstance(value, list):
                raise serializers.ValidationError("asset_ids must be a list")
            if len(value) == 0:
                raise serializers.ValidationError("asset_ids cannot be empty for PUSH direction")
        return value

    def validate_listing_ids(self, value):
        """Validate listing_ids if provided"""
        if value is not None:
            if not isinstance(value, list):
                raise serializers.ValidationError("listing_ids must be a list")
        return value

    def validate_filters(self, value):
        """Validate filters is a dictionary if provided"""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("filters must be a JSON object (dictionary)")
        return value

    def validate_options(self, value):
        """Validate options is a dictionary if provided"""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("options must be a JSON object (dictionary)")
        return value

    def validate(self, attrs):
        """Cross-field validation"""
        direction = attrs.get('direction')
        asset_ids = attrs.get('asset_ids')
        listing_ids = attrs.get('listing_ids')

        if direction == SyncDirection.PUSH.value:
            # PUSH direction requires asset_ids
            if not asset_ids:
                raise serializers.ValidationError({
                    'asset_ids': 'asset_ids is required for PUSH direction'
                })
        elif direction == SyncDirection.PULL.value:
            # PULL direction can have listing_ids or filters, but not asset_ids
            if asset_ids:
                raise serializers.ValidationError({
                    'asset_ids': 'asset_ids cannot be used with PULL direction. Use listing_ids or filters instead.'
                })
        elif direction == SyncDirection.BIDIRECTIONAL.value:
            # BIDIRECTIONAL requires both asset_ids and listing_ids/filters
            if not asset_ids:
                raise serializers.ValidationError({
                    'asset_ids': 'asset_ids is required for BIDIRECTIONAL direction'
                })

        return attrs


class MarketplaceSyncJobCancelSerializer(serializers.Serializer):
    """
    Serializer for cancelling a marketplace sync job.
    """
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Optional reason for cancellation"
    )


class MarketplaceMappingSerializer(serializers.ModelSerializer):
    """
    Serializer for MarketplaceMapping model (read operations).

    Provides read-only access to marketplace mappings with related entity information.
    """
    tenant = serializers.UUIDField(
        source='tenant.id',
        read_only=True,
        help_text="Tenant ID"
    )
    tenant_name = serializers.CharField(
        source='tenant.name',
        read_only=True,
        help_text="Tenant name"
    )
    connection_id = serializers.UUIDField(
        source='connection.id',
        read_only=True,
        help_text="Connection ID"
    )
    connection_name = serializers.CharField(
        source='connection.name',
        read_only=True,
        help_text="Connection name"
    )
    hub_asset_id = serializers.UUIDField(
        source='hub_asset.id',
        read_only=True,
        help_text="Hub asset ID"
    )
    hub_asset_name = serializers.CharField(
        source='hub_asset.name',
        read_only=True,
        help_text="Hub asset name"
    )
    hub_asset_key = serializers.CharField(
        source='hub_asset.key',
        read_only=True,
        help_text="Hub asset key"
    )

    class Meta:
        model = MarketplaceMapping
        fields = [
            'id',
            'tenant',
            'tenant_name',
            'connection_id',
            'connection_name',
            'hub_asset_id',
            'hub_asset_name',
            'hub_asset_key',
            'external_listing_id',
            'external_resource_ids',
            'sync_metadata',
            'last_synced_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'tenant',
            'tenant_name',
            'connection_id',
            'connection_name',
            'hub_asset_id',
            'hub_asset_name',
            'hub_asset_key',
            'external_listing_id',
            'external_resource_ids',
            'sync_metadata',
            'last_synced_at',
            'created_at',
            'updated_at',
        ]

