"""
GDPR Serializers

Serializers for data export and erasure requests.
"""

from rest_framework import serializers

from hub.apps.gdpr.models import DataExportJob, ErasureRequest


class DataExportJobSerializer(serializers.ModelSerializer):
    """Serializer for DataExportJob model"""

    class Meta:
        model = DataExportJob
        fields = [
            "id",
            "user",
            "tenant",
            "status",
            "storage_path",
            "download_url",
            "download_url_expires_at",
            "error_message",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "tenant",
            "storage_path",
            "download_url",
            "download_url_expires_at",
            "error_message",
            "created_at",
            "updated_at",
            "completed_at",
        ]


class ErasureRequestSerializer(serializers.ModelSerializer):
    """Serializer for ErasureRequest model"""

    class Meta:
        model = ErasureRequest
        fields = [
            "id",
            "user",
            "tenant",
            "status",
            "requested_at",
            "completed_at",
            "error_message",
            "anonymized_fields",
            "deleted_resources",
            "retention_exceptions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "tenant",
            "status",
            "requested_at",
            "completed_at",
            "error_message",
            "anonymized_fields",
            "deleted_resources",
            "retention_exceptions",
            "created_at",
            "updated_at",
        ]
