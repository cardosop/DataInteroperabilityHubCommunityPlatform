"""
Scheduled Export Serializers

DRF serializers for scheduled export API endpoints.
"""

from rest_framework import serializers

from .models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from hub.apps.virtualization.source_config_utils import mask_source_config


class ScheduledExportSerializer(serializers.ModelSerializer):
    """Serializer for ScheduledExport model"""

    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = ScheduledExport
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "name",
            "schedule_config",
            "destination_type",
            "destination_config",
            "source_scope",
            "status",
            "next_run_at",
            "last_run_at",
            "last_run_status",
            "prefect_deployment_id",
            "deployment_sync_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant_name",
            "next_run_at",
            "last_run_at",
            "last_run_status",
            "prefect_deployment_id",
            "deployment_sync_status",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        """Decrypt and mask sensitive fields in destination_config."""
        ret = super().to_representation(instance)
        ret["destination_config"] = mask_source_config(
            instance.get_destination_config()
        )
        return ret

    def validate_schedule_config(self, value):
        """Validate schedule configuration"""
        cron_expr = value.get("cron")
        if not cron_expr:
            raise serializers.ValidationError("Cron expression is required in schedule_config")

        try:
            from croniter import croniter

            croniter(cron_expr)
        except Exception as e:
            raise serializers.ValidationError(f"Invalid cron expression: {str(e)}")

        return value

    def validate_source_scope(self, value):
        """Validate source scope structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("source_scope must be a dictionary")

        valid_scope_fields = ["asset_ids", "dataset_ids", "file_ids", "contract_id"]
        has_scope = any(field in value and value[field] for field in valid_scope_fields)
        if not has_scope:
            raise serializers.ValidationError(
                "source_scope must contain at least one of: asset_ids, dataset_ids, file_ids, contract_id"
            )

        return value

    def validate_destination_config(self, value):
        """Validate destination configuration"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("destination_config must be a dictionary")

        return value


class ScheduledExportCreateSerializer(ScheduledExportSerializer):
    """Serializer for creating scheduled export"""

    class Meta(ScheduledExportSerializer.Meta):
        # Tenant is set by ViewSet, not required in request
        extra_kwargs = {"tenant": {"required": False, "read_only": True}}


class ScheduledExportRunSerializer(serializers.ModelSerializer):
    """Serializer for ScheduledExportRun model"""

    scheduled_export_name = serializers.CharField(source="scheduled_export.name", read_only=True)

    class Meta:
        model = ScheduledExportRun
        fields = [
            "id",
            "scheduled_export",
            "scheduled_export_name",
            "status",
            "items_found",
            "items_exported",
            "items_failed",
            "result_json",
            "started_at",
            "completed_at",
            "prefect_flow_run_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "scheduled_export_name",
            "status",
            "items_found",
            "items_exported",
            "items_failed",
            "result_json",
            "started_at",
            "completed_at",
            "prefect_flow_run_id",
            "created_at",
            "updated_at",
        ]


class ScheduledExportTriggerSerializer(serializers.Serializer):
    """Serializer for triggering scheduled export manually"""

    parameters = serializers.DictField(
        required=False, default=dict, help_text="Optional flow run parameters"
    )
