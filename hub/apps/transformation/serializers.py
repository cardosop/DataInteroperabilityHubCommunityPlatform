"""
Transformation Serializers

DRF serializers for Transformation Pipeline API.
"""
from rest_framework import serializers
from .models import (
    TransformationPipeline, PipelineStatus, PipelineExecution, ExecutionStatus, ExecutionMode,
    PreviewResult, WranglingSession, WranglingOperation, WranglingOperationType
)


class TransformationPipelineSerializer(serializers.ModelSerializer):
    """Serializer for TransformationPipeline model"""

    status = serializers.ChoiceField(choices=PipelineStatus.choices, read_only=True)

    class Meta:
        model = TransformationPipeline
        fields = [
            'id',
            'tenant',
            'created_by',
            'name',
            'description',
            'pipeline_definition',
            'version',
            'status',
            'created_at',
            'updated_at',
            'metadata',
        ]
        read_only_fields = [
            'id',
            'tenant',
            'created_by',
            'created_at',
            'updated_at',
        ]


class TransformationPipelineCreateSerializer(serializers.Serializer):
    """Serializer for pipeline creation"""
    name = serializers.CharField(
        max_length=255,
        help_text="Pipeline name (e.g., 'Customer Data Enrichment', 'Sales Aggregation')"
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Pipeline description and purpose"
    )
    pipeline_definition = serializers.DictField(
        help_text="Complete pipeline definition (JSON format) including nodes, connections, transformations"
    )
    version = serializers.CharField(
        max_length=50,
        default="1.0.0",
        required=False,
        help_text="Pipeline version (semantic versioning: major.minor.patch)"
    )
    status = serializers.ChoiceField(
        choices=PipelineStatus.choices,
        default=PipelineStatus.DRAFT,
        required=False,
        help_text="Pipeline status: DRAFT, ACTIVE, INACTIVE, ARCHIVED"
    )
    metadata = serializers.DictField(
        required=False,
        default=dict,
        allow_empty=True,
        help_text="Additional metadata (tags, categories, source/target assets, etc.)"
    )

    def validate_pipeline_definition(self, value):
        """Validate pipeline_definition structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Pipeline definition must be a JSON object"
            )

        # Validate required fields
        required_fields = ["version", "steps"]
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(
                    f"Pipeline definition must contain '{field}' field"
                )

        # Validate version format
        version_str = value.get("version", "")
        if not isinstance(version_str, str) or not version_str.strip():
            raise serializers.ValidationError(
                "Pipeline definition 'version' must be a non-empty string"
            )

        # Validate steps is a list
        steps = value.get("steps", [])
        if not isinstance(steps, list):
            raise serializers.ValidationError(
                "Pipeline definition 'steps' must be a list"
            )

        if len(steps) == 0:
            raise serializers.ValidationError(
                "Pipeline definition must have at least one step"
            )

        # Validate each step has required fields
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                raise serializers.ValidationError(
                    f"Step {i} must be a JSON object"
                )

            if "name" not in step:
                raise serializers.ValidationError(
                    f"Step {i} must have a 'name' field"
                )

            if "type" not in step:
                raise serializers.ValidationError(
                    f"Step {i} must have a 'type' field"
                )

        return value


class TransformationPipelineUpdateSerializer(serializers.Serializer):
    """Serializer for pipeline update"""
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )
    pipeline_definition = serializers.DictField(required=False)
    version = serializers.CharField(max_length=50, required=False)
    status = serializers.ChoiceField(choices=PipelineStatus.choices, required=False)
    metadata = serializers.DictField(required=False, allow_empty=True)

    def validate_pipeline_definition(self, value):
        """Validate pipeline_definition structure if provided"""
        if value is None:
            return value

        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Pipeline definition must be a JSON object"
            )

        # Validate required fields
        required_fields = ["version", "steps"]
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(
                    f"Pipeline definition must contain '{field}' field"
                )

        # Validate version format
        version_str = value.get("version", "")
        if not isinstance(version_str, str) or not version_str.strip():
            raise serializers.ValidationError(
                "Pipeline definition 'version' must be a non-empty string"
            )

        # Validate steps is a list
        steps = value.get("steps", [])
        if not isinstance(steps, list):
            raise serializers.ValidationError(
                "Pipeline definition 'steps' must be a list"
            )

        if len(steps) == 0:
            raise serializers.ValidationError(
                "Pipeline definition must have at least one step"
            )

        # Validate each step has required fields
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                raise serializers.ValidationError(
                    f"Step {i} must be a JSON object"
                )

            if "name" not in step:
                raise serializers.ValidationError(
                    f"Step {i} must have a 'name' field"
                )

            if "type" not in step:
                raise serializers.ValidationError(
                    f"Step {i} must have a 'type' field"
                )

        return value


class PipelineValidationResponseSerializer(serializers.Serializer):
    """Serializer for pipeline validation response"""
    is_valid = serializers.BooleanField()
    errors = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True
    )
    warnings = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True
    )
    details = serializers.DictField(allow_empty=True)


class PipelineExecutionSerializer(serializers.ModelSerializer):
    """Serializer for PipelineExecution model"""

    status = serializers.ChoiceField(choices=ExecutionStatus.choices, read_only=True)
    execution_mode = serializers.ChoiceField(choices=ExecutionMode.choices, read_only=True)
    pipeline_id = serializers.UUIDField(source='pipeline.id', read_only=True)
    pipeline_name = serializers.CharField(source='pipeline.name', read_only=True)
    asset_id = serializers.UUIDField(source='asset.id', read_only=True)
    asset_name = serializers.CharField(source='asset.name', read_only=True)
    result_asset_id = serializers.UUIDField(source='result_asset.id', read_only=True, allow_null=True)
    result_asset_name = serializers.CharField(source='result_asset.name', read_only=True, allow_null=True)
    job_id = serializers.UUIDField(source='job.id', read_only=True, allow_null=True)
    duration_seconds = serializers.FloatField(read_only=True, allow_null=True)

    class Meta:
        model = PipelineExecution
        fields = [
            'id',
            'pipeline_id',
            'pipeline_name',
            'asset_id',
            'asset_name',
            'execution_mode',
            'status',
            'started_at',
            'completed_at',
            'result_asset_id',
            'result_asset_name',
            'job_id',
            'execution_log',
            'metrics',
            'idempotency_key',
            'created_at',
            'updated_at',
            'duration_seconds',
        ]
        read_only_fields = [
            'id',
            'pipeline_id',
            'pipeline_name',
            'asset_id',
            'asset_name',
            'execution_mode',
            'status',
            'started_at',
            'completed_at',
            'result_asset_id',
            'result_asset_name',
            'job_id',
            'execution_log',
            'metrics',
            'idempotency_key',
            'created_at',
            'updated_at',
            'duration_seconds',
        ]

    def to_representation(self, instance):
        """Add computed fields"""
        representation = super().to_representation(instance)
        representation['duration_seconds'] = instance.get_duration_seconds()
        return representation


class PipelineExecutionProgressSerializer(serializers.Serializer):
    """Serializer for execution progress response"""
    execution_id = serializers.UUIDField()
    status = serializers.CharField()
    progress_percentage = serializers.FloatField(allow_null=True)
    current_step = serializers.CharField(allow_null=True, allow_blank=True)
    total_steps = serializers.IntegerField(allow_null=True)
    started_at = serializers.DateTimeField(allow_null=True)
    estimated_completion_at = serializers.DateTimeField(allow_null=True)
    duration_seconds = serializers.FloatField(allow_null=True)
    metrics = serializers.DictField(allow_empty=True)
    recent_logs = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=True
    )


class PipelineExecutionResultSerializer(serializers.Serializer):
    """Serializer for execution result response"""
    execution_id = serializers.UUIDField()
    status = serializers.CharField()
    result_asset_id = serializers.UUIDField(allow_null=True)
    result_asset_name = serializers.CharField(allow_null=True, allow_blank=True)
    metrics = serializers.DictField(allow_empty=True)
    execution_log = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=True
    )
    started_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    duration_seconds = serializers.FloatField(allow_null=True)
    error_message = serializers.CharField(allow_null=True, allow_blank=True)


class PreviewResultSerializer(serializers.ModelSerializer):
    """Serializer for PreviewResult model"""

    pipeline_id = serializers.UUIDField(source='pipeline.id', read_only=True)
    pipeline_name = serializers.CharField(source='pipeline.name', read_only=True)
    asset_id = serializers.UUIDField(source='asset.id', read_only=True)
    asset_name = serializers.CharField(source='asset.name', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = PreviewResult
        fields = [
            'id',
            'preview_id',
            'pipeline_id',
            'pipeline_name',
            'asset_id',
            'asset_name',
            'preview_data',
            'sample_size',
            'sampling_method',
            'generated_at',
            'expires_at',
            'is_expired',
        ]
        read_only_fields = [
            'id',
            'preview_id',
            'pipeline_id',
            'pipeline_name',
            'asset_id',
            'asset_name',
            'preview_data',
            'sample_size',
            'sampling_method',
            'generated_at',
            'expires_at',
            'is_expired',
        ]

    def to_representation(self, instance):
        """Add computed fields"""
        representation = super().to_representation(instance)
        representation['is_expired'] = instance.is_expired()
        return representation


class WranglingOperationRequestSerializer(serializers.Serializer):
    """Serializer for wrangling operation request"""
    asset_id = serializers.UUIDField(help_text="Source asset ID")
    operation = serializers.DictField(
        help_text="Operation definition with 'type' and 'parameters'"
    )
    session_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional wrangling session ID (creates new if not provided)"
    )

    def validate_operation(self, value):
        """Validate operation structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Operation must be a dictionary")

        if "type" not in value:
            raise serializers.ValidationError("Operation must have 'type' field")

        operation_type = value.get("type")
        valid_types = [op[0] for op in WranglingOperationType.choices]
        if operation_type not in valid_types:
            raise serializers.ValidationError(
                f"Invalid operation type: {operation_type}. Valid types: {', '.join(valid_types)}"
            )

        if "parameters" not in value:
            raise serializers.ValidationError("Operation must have 'parameters' field")

        if not isinstance(value.get("parameters"), dict):
            raise serializers.ValidationError("Operation parameters must be a dictionary")

        return value


class WranglingSessionSerializer(serializers.ModelSerializer):
    """Serializer for WranglingSession model"""

    asset_id = serializers.UUIDField(source='asset.id', read_only=True)
    asset_name = serializers.CharField(source='asset.name', read_only=True)
    can_undo = serializers.BooleanField(read_only=True)
    can_redo = serializers.BooleanField(read_only=True)
    applied_operations_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = WranglingSession
        fields = [
            'id',
            'name',
            'description',
            'asset_id',
            'asset_name',
            'current_state',
            'operation_history',
            'history_position',
            'wrangling_script',
            'metadata',
            'can_undo',
            'can_redo',
            'applied_operations_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'asset_id',
            'asset_name',
            'current_state',
            'operation_history',
            'history_position',
            'wrangling_script',
            'metadata',
            'can_undo',
            'can_redo',
            'applied_operations_count',
            'created_at',
            'updated_at',
        ]

    def to_representation(self, instance):
        """Add computed fields"""
        representation = super().to_representation(instance)
        representation['can_undo'] = instance.can_undo()
        representation['can_redo'] = instance.can_redo()
        representation['applied_operations_count'] = len(instance.get_applied_operations())
        return representation


class WranglingResultSerializer(serializers.Serializer):
    """Serializer for wrangling operation result response"""
    session_id = serializers.UUIDField()
    operation_id = serializers.UUIDField(allow_null=True)
    result = serializers.DictField(
        help_text="Operation result (sample_data, row counts, columns)"
    )
    can_undo = serializers.BooleanField()
    can_redo = serializers.BooleanField()
    applied_operations_count = serializers.IntegerField()
    wrangling_script = serializers.CharField(allow_null=True, allow_blank=True)


