"""
Internal Worker API Serializers

Request/response serializers for scheduled export internal endpoints.
"""

from rest_framework import serializers

from .models import ScheduledExportRunStatus


class InternalCreateExportRunSerializer(serializers.Serializer):
    """Request body for POST .../internal/runs/ (scheduled export)."""

    scheduled_export_id = serializers.UUIDField(required=True)
    prefect_flow_run_id = serializers.CharField(required=False, allow_blank=True, max_length=255)
    idempotency_key = serializers.CharField(required=False, allow_blank=True, max_length=255)


class InternalUpdateExportRunSerializer(serializers.Serializer):
    """Request body for PATCH .../internal/runs/{run_id}/ (scheduled export)."""

    status = serializers.ChoiceField(
        choices=[s[0] for s in ScheduledExportRunStatus.choices],
        required=False,
    )
    items_found = serializers.IntegerField(required=False, min_value=0)
    items_exported = serializers.IntegerField(required=False, min_value=0)
    items_failed = serializers.IntegerField(required=False, min_value=0)
    result_json = serializers.JSONField(required=False)
    completed_at = serializers.DateTimeField(required=False)
    prefect_flow_run_id = serializers.CharField(required=False, allow_blank=True, max_length=255)


class InternalProcessExportSerializer(serializers.Serializer):
    """Request body for POST .../internal/process-export/"""

    run_id = serializers.UUIDField(required=True)
    dataset_id = serializers.UUIDField(required=False, allow_null=True)
    file_id = serializers.UUIDField(required=False, allow_null=True)
    destination_path = serializers.CharField(required=False, allow_blank=True, max_length=500)
    destination_options = serializers.JSONField(required=False, default=dict)
