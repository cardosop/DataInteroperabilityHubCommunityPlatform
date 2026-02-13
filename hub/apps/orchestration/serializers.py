"""
Serializers for Workflows API (list, retrieve, trigger).
"""

from rest_framework import serializers

from .models import WorkflowDefinition


class WorkflowDefinitionListSerializer(serializers.ModelSerializer):
    """Serializer for workflow definition in list responses."""

    class Meta:
        model = WorkflowDefinition
        fields = [
            "id",
            "name",
            "version",
            "description",
            "is_active",
            "dependencies",
            "metadata",
            "created_at",
        ]


class WorkflowDefinitionDetailSerializer(serializers.ModelSerializer):
    """Serializer for workflow definition detail (retrieve)."""

    class Meta:
        model = WorkflowDefinition
        fields = [
            "id",
            "name",
            "version",
            "description",
            "dsl_json",
            "is_active",
            "dependencies",
            "metadata",
            "created_at",
            "updated_at",
        ]


class WorkflowTriggerRequestSerializer(serializers.Serializer):
    """Request body for POST .../trigger/."""

    input_data = serializers.JSONField(default=dict, help_text="Workflow input data")
    start_immediately = serializers.BooleanField(
        default=False,
        required=False,
        help_text="If true, start instance after creation",
    )

    def validate_input_data(self, value):
        """Engine and model expect a JSON object (dict)."""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("input_data must be an object (dict).")
        return value or {}


class WorkflowTriggerResponseSerializer(serializers.Serializer):
    """Response for POST .../trigger/."""

    id = serializers.UUIDField(read_only=True)
    status = serializers.CharField(read_only=True)
    workflow_name = serializers.CharField(read_only=True)
    workflow_version = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
