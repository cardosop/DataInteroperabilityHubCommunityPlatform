"""285.6.2 — Data movement serializers."""

from rest_framework import serializers

from .models import DataMovementConfig


class DataMovementConfigSerializer(serializers.ModelSerializer):
    """Per-tenant dlt data movement configuration."""

    class Meta:
        model = DataMovementConfig
        fields = (
            "tenant",
            "dlt_dev_mode",
            "max_parallel_pipelines",
            "created_at",
            "updated_at",
        )
        # tenant is derived from the authenticated request, never from the body.
        read_only_fields = ("tenant", "created_at", "updated_at")
