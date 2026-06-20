"""
Internal Worker API Serializers

Request/response serializers for scheduled ingestion internal endpoints.
"""

from rest_framework import serializers

from .models import ScheduledIngestionRunStatus


class InternalCreateIngestionRunSerializer(serializers.Serializer):
    """Request body for POST .../internal/runs/ (scheduled ingestion)."""

    scheduled_ingestion_id = serializers.UUIDField(required=True)
    prefect_flow_run_id = serializers.CharField(required=False, allow_blank=True, max_length=255)
    idempotency_key = serializers.CharField(required=False, allow_blank=True, max_length=255)


class InternalUpdateIngestionRunSerializer(serializers.Serializer):
    """Request body for PATCH .../internal/runs/{run_id}/ (scheduled ingestion)."""

    status = serializers.ChoiceField(
        choices=[s[0] for s in ScheduledIngestionRunStatus.choices],
        required=False,
    )
    files_found = serializers.IntegerField(required=False, min_value=0)
    files_processed = serializers.IntegerField(required=False, min_value=0)
    files_failed = serializers.IntegerField(required=False, min_value=0)
    result_json = serializers.JSONField(required=False)
    completed_at = serializers.DateTimeField(required=False)
    prefect_flow_run_id = serializers.CharField(required=False, allow_blank=True, max_length=255)
    error_message = serializers.CharField(required=False, allow_blank=True)


class InternalProcessFileSerializer(serializers.Serializer):
    """Request for POST .../internal/process-file/ (multipart or JSON with base64 file_content)."""

    run_id = serializers.UUIDField(required=True)
    file_path = serializers.CharField(required=True, max_length=500)
    asset_id = serializers.UUIDField(required=False)
    contract_id = serializers.UUIDField(required=False)
    dq_options = serializers.JSONField(required=False, default=dict)
    # file is provided via multipart; or file_content (base64) in JSON
    file_content = serializers.CharField(required=False, allow_blank=True)


class InternalCreateJobSerializer(serializers.Serializer):
    """Request body for POST .../internal/jobs/ — create Job (type SCHEDULED_INGESTION) executed by Prefect; no RQ enqueue."""

    scheduled_ingestion_id = serializers.UUIDField(required=True)
    prefect_flow_run_id = serializers.CharField(required=True, allow_blank=False, max_length=255)
    scheduled_ingestion_run_id = serializers.UUIDField(required=False, allow_null=True)
