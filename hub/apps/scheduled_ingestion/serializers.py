"""
Scheduled Ingestion Serializers

DRF serializers for scheduled ingestion API endpoints.
"""
from rest_framework import serializers
from django.utils import timezone
from .models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    SourceType,
    ScheduleType,
    ScheduledIngestionStatus,
    ScheduledIngestionRunStatus
)


class ScheduledIngestionSerializer(serializers.ModelSerializer):
    """Serializer for ScheduledIngestion model"""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    asset_name = serializers.CharField(source='asset.name', read_only=True, allow_null=True)
    contract_name = serializers.CharField(source='contract.name', read_only=True, allow_null=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    asset_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    # allow_blank so empty/whitespace name reaches service (ScheduledIngestionBusinessRules)
    name = serializers.CharField(max_length=255, allow_blank=True)
    
    class Meta:
        model = ScheduledIngestion
        fields = [
            'id',
            'tenant',
            'tenant_name',
            'name',
            'description',
            'source_type',
            'source_config',
            'schedule_type',
            'schedule_config',
            'file_pattern',
            'asset',
            'asset_id',
            'asset_name',
            'contract',
            'contract_name',
            'auto_create_asset',
            'auto_activate',
            'status',
            'next_run_at',
            'prefect_deployment_id',
            'prefect_work_pool_name',
            'last_processed_file',
            'last_processed_timestamp',
            'ingestion_state',
            'error_message',
            'created_by',
            'created_by_username',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'tenant',
            'tenant_name',
            'asset_name',
            'contract_name',
            'created_by_username',
            'next_run_at',
            'prefect_deployment_id',
            'last_processed_file',
            'last_processed_timestamp',
            'ingestion_state',
            'error_message',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            # API requires file_pattern on create/update; model allows null/blank for match-all (.*)
            'file_pattern': {'required': True, 'allow_blank': True},
        }
    
    def validate_file_pattern(self, value):
        """Validate file pattern is a valid regex. None/blank allowed (means match-all in processor)."""
        if value is None or value == "":
            return value
        import re
        try:
            re.compile(value)
        except re.error as e:
            raise serializers.ValidationError(f"Invalid file pattern regex: {str(e)}")
        return value
    
    def validate_schedule_config(self, value):
        """Validate schedule configuration"""
        schedule_type = self.initial_data.get('schedule_type', ScheduleType.DAILY)
        
        if schedule_type == ScheduleType.CUSTOM_CRON:
            cron_expr = value.get('cron')
            if not cron_expr:
                raise serializers.ValidationError("Cron expression is required for CUSTOM_CRON schedule type")
            
            try:
                from croniter import croniter
                croniter(cron_expr)
            except Exception as e:
                raise serializers.ValidationError(f"Invalid cron expression: {str(e)}")
        
        return value
    
    def validate_source_config(self, value):
        """Validate source configuration"""
        source_type = self.initial_data.get('source_type')
        
        if not source_type:
            return value
        
        # Basic validation based on source type
        if source_type == SourceType.S3:
            if not value.get('bucket'):
                raise serializers.ValidationError("S3 bucket is required")
        elif source_type == SourceType.GCS:
            if not value.get('bucket'):
                raise serializers.ValidationError("GCS bucket is required")
        elif source_type == SourceType.AZURE_BLOB:
            if not value.get('account_name') or not value.get('container'):
                raise serializers.ValidationError("Azure account_name and container are required")
        elif source_type in [SourceType.HTTP, SourceType.HTTPS]:
            if not value.get('base_url'):
                raise serializers.ValidationError("HTTP base_url is required")
        elif source_type in [SourceType.FTP, SourceType.SFTP]:
            if not value.get('host'):
                raise serializers.ValidationError("FTP/SFTP host is required")
        elif source_type == SourceType.DATABASE:
            if not value.get('host') or not value.get('database'):
                raise serializers.ValidationError("Database host and database name are required")
        
        return value
    
    def validate(self, attrs):
        """Validate and convert asset_id to asset"""
        attrs = super().validate(attrs)
        
        # Convert asset_id to asset if provided
        asset_id = attrs.pop('asset_id', None)
        if asset_id is not None:
            from hub.apps.assets.models import Asset
            try:
                asset = Asset.objects.get(id=asset_id)
                attrs['asset'] = asset
            except Asset.DoesNotExist:
                raise serializers.ValidationError({'asset_id': f'Asset with id {asset_id} does not exist'})
        
        return attrs


class ScheduledIngestionRunSerializer(serializers.ModelSerializer):
    """Serializer for ScheduledIngestionRun model"""
    
    scheduled_ingestion_name = serializers.CharField(
        source='scheduled_ingestion.name',
        read_only=True
    )
    
    class Meta:
        model = ScheduledIngestionRun
        fields = [
            'id',
            'scheduled_ingestion',
            'scheduled_ingestion_name',
            'status',
            'started_at',
            'completed_at',
            'prefect_flow_run_id',
            'job_id',
            'files_found',
            'files_processed',
            'files_failed',
            'datasets_created',
            'error_message',
            'result_json',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'scheduled_ingestion_name',
            'status',
            'started_at',
            'completed_at',
            'files_found',
            'files_processed',
            'files_failed',
            'datasets_created',
            'error_message',
            'result_json',
            'created_at',
            'updated_at',
        ]


class ScheduledIngestionCreateSerializer(ScheduledIngestionSerializer):
    """Serializer for creating scheduled ingestion (with connection test)"""
    
    test_connection = serializers.BooleanField(
        default=True,
        write_only=True,
        help_text="Test source connection before creating scheduled ingestion"
    )
    
    class Meta(ScheduledIngestionSerializer.Meta):
        fields = ScheduledIngestionSerializer.Meta.fields + ['test_connection']
        # Tenant is set by ViewSet.perform_create, not required in request
        extra_kwargs = {
            'tenant': {'required': False, 'read_only': True}
        }
    
    def validate(self, attrs):
        """Validate and test connection if requested"""
        attrs = super().validate(attrs)
        test_connection = attrs.get('test_connection', True)

        if test_connection:
            source_type = attrs.get('source_type')
            source_config = attrs.get('source_config')
            
            if source_type and source_config:
                try:
                    import sys
                    import os
                    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../services/prefect-integration'))
                    from connectors.factory import SourceConnectorFactory
                    
                    connector = SourceConnectorFactory.get_connector(source_type)
                    if not connector.test_connection(source_config):
                        raise serializers.ValidationError({
                            'source_config': 'Connection test failed. Please check your source configuration.'
                        })
                except ImportError:
                    # Connector factory not available (e.g., in test environment)
                    # Skip connection test if factory is not available
                    pass
                except Exception as e:
                    # Connection test failed - return validation error instead of raising 500
                    raise serializers.ValidationError({
                        'source_config': f'Connection test failed: {str(e)}'
                    })

        # Remove so it is never in validated_data or passed to create()
        attrs.pop('test_connection', None)
        return attrs
    
    def create(self, validated_data):
        """Create scheduled ingestion, excluding test_connection field"""
        # Remove test_connection from validated_data as it's not a model field
        validated_data.pop('test_connection', None)
        # Call parent create method
        return super().create(validated_data)


class ScheduledIngestionTriggerSerializer(serializers.Serializer):
    """Serializer for triggering scheduled ingestion manually"""
    
    parameters = serializers.DictField(
        required=False,
        default=dict,
        help_text="Optional flow run parameters"
    )

