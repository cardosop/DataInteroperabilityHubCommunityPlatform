from __future__ import annotations

from rest_framework import serializers

from hub.apps.ropa.models import RopaGeneration


class RopaGenerationSerializer(serializers.ModelSerializer):
    job = serializers.UUIDField(source="job_id", allow_null=True, read_only=True)

    class Meta:
        model = RopaGeneration
        fields = [
            "id",
            "regulation",
            "output_format",
            "status",
            "byte_size",
            "content_sha256",
            "gaps_json",
            "summary_json",
            "job",
            "created_at",
            "completed_at",
            "error_message",
        ]
        read_only_fields = [
            "id",
            "regulation",
            "output_format",
            "status",
            "byte_size",
            "content_sha256",
            "job",
            "created_at",
            "completed_at",
            "error_message",
        ]
