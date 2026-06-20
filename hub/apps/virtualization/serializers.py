"""
Virtualization Serializers

REST API serializers for virtual dataset management.
"""

from rest_framework import serializers

from .models import (
    QueryExecution,
    QueryExecutionMode,
    QueryType,
    VirtualDataset,
    VirtualDatasetStatus,
)
from .source_config_utils import mask_sources_for_api


class VirtualDatasetSerializer(serializers.ModelSerializer):
    """Serializer for VirtualDataset model."""

    class Meta:
        model = VirtualDataset
        fields = [
            "id",
            "tenant",
            "created_by",
            "name",
            "description",
            "query",
            "query_type",
            "schema",
            "sources",
            "version",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "created_by", "version", "created_at", "updated_at"]

    def to_representation(self, instance):
        """Decrypt and mask sensitive fields in sources."""
        ret = super().to_representation(instance)
        # Use decrypted sources from model method
        ret["sources"] = mask_sources_for_api(instance.get_sources())
        return ret


class VirtualDatasetCreateSerializer(serializers.Serializer):
    """Serializer for virtual dataset creation with comprehensive validation"""

    name = serializers.CharField(
        max_length=255, help_text="Virtual dataset name (unique per tenant)"
    )
    description = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, help_text="Virtual dataset description"
    )
    query = serializers.CharField(help_text="Query definition (SQL, SPARQL, federated query, etc.)")
    query_type = serializers.ChoiceField(
        choices=QueryType.choices, help_text="Type of query: SQL, SPARQL, FEDERATED, GRAPHQL, REST"
    )
    schema = serializers.JSONField(
        required=False,
        allow_null=True,
        help_text="Output schema definition as JSON (fields, types, constraints, etc.)",
    )
    sources = serializers.JSONField(
        required=False,
        allow_null=True,
        help_text="Source system configurations as JSON array (connection details, mappings, etc.)",
    )
    version = serializers.CharField(
        max_length=50,
        required=False,
        default="1.0.0",
        help_text="Virtual dataset version (semantic versioning: major.minor.patch)",
    )
    status = serializers.ChoiceField(
        choices=VirtualDatasetStatus.choices,
        required=False,
        default=VirtualDatasetStatus.DRAFT,
        help_text="Virtual dataset status: DRAFT, ACTIVE, INACTIVE, ARCHIVED",
    )

    def validate_name(self, value):
        """Validate dataset name"""
        if not value or not value.strip():
            raise serializers.ValidationError("Virtual dataset name cannot be empty")
        if len(value.strip()) < 1:
            raise serializers.ValidationError("Virtual dataset name must be at least 1 character")
        if len(value.strip()) > 255:
            raise serializers.ValidationError("Virtual dataset name cannot exceed 255 characters")
        return value.strip()

    def validate_query(self, value):
        """Validate query is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Query definition cannot be empty")
        return value.strip()

    def validate_schema(self, value):
        """Validate schema is a dictionary if provided"""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Schema must be a JSON object (dictionary)")
        return value

    def validate_sources(self, value):
        """Validate sources is a list if provided"""
        if value is not None and not isinstance(value, list):
            raise serializers.ValidationError("Sources must be a JSON array (list)")
        return value

    def validate_version(self, value):
        """Validate version follows semantic versioning format"""
        if not value:
            return "1.0.0"

        version_parts = value.split(".")
        if len(version_parts) != 3:
            raise serializers.ValidationError(
                "Version must follow semantic versioning format (major.minor.patch), e.g., '1.0.0'"
            )

        try:
            int(version_parts[0])  # major
            int(version_parts[1])  # minor
            int(version_parts[2])  # patch
        except ValueError:
            raise serializers.ValidationError("Version parts must be numeric (e.g., '1.0.0')")

        return value

    def validate(self, attrs):
        """Cross-field validation"""
        query = attrs.get("query", "")
        query_type = attrs.get("query_type")

        if query and query_type:
            query_upper = query.upper().strip()

            # Basic query type validation
            if query_type == QueryType.SQL:
                if not any(
                    keyword in query_upper
                    for keyword in ["SELECT", "WITH", "INSERT", "UPDATE", "DELETE"]
                ):
                    raise serializers.ValidationError(
                        {
                            "query": "SQL query should contain SQL keywords (SELECT, WITH, INSERT, UPDATE, DELETE)"
                        }
                    )
            elif query_type == QueryType.SPARQL:
                if not any(
                    keyword in query_upper
                    for keyword in ["SELECT", "CONSTRUCT", "ASK", "DESCRIBE", "PREFIX"]
                ):
                    raise serializers.ValidationError(
                        {
                            "query": "SPARQL query should contain SPARQL keywords (SELECT, CONSTRUCT, ASK, DESCRIBE, PREFIX)"
                        }
                    )

        return attrs


class VirtualDatasetUpdateSerializer(serializers.Serializer):
    """Serializer for virtual dataset update with comprehensive validation"""

    name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="Virtual dataset name (empty/whitespace rejected by service layer)",
    )
    description = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, help_text="Virtual dataset description"
    )
    query = serializers.CharField(required=False, help_text="Query definition")
    query_type = serializers.ChoiceField(
        choices=QueryType.choices, required=False, help_text="Type of query"
    )
    schema = serializers.JSONField(
        required=False, allow_null=True, help_text="Output schema definition"
    )
    sources = serializers.JSONField(
        required=False, allow_null=True, help_text="Source system configurations"
    )
    version = serializers.CharField(
        max_length=50,
        required=False,
        help_text="Virtual dataset version (semantic versioning: major.minor.patch)",
    )
    status = serializers.ChoiceField(
        choices=VirtualDatasetStatus.choices, required=False, help_text="Virtual dataset status"
    )

    def validate_name(self, value):
        """Pass through name; empty/whitespace rejected by VirtualizationBusinessRules in service."""
        if value is not None and isinstance(value, str):
            if value.strip() and len(value.strip()) > 255:
                raise serializers.ValidationError(
                    "Virtual dataset name cannot exceed 255 characters"
                )
            return value.strip() if value.strip() else value
        return value

    def validate_query(self, value):
        """Validate query if provided"""
        if value is not None and not value.strip():
            raise serializers.ValidationError("Query definition cannot be empty")
        return value.strip() if value else value

    def validate_schema(self, value):
        """Validate schema is a dictionary if provided"""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Schema must be a JSON object (dictionary)")
        return value

    def validate_sources(self, value):
        """Validate sources is a list if provided"""
        if value is not None and not isinstance(value, list):
            raise serializers.ValidationError("Sources must be a JSON array (list)")
        return value

    def validate_version(self, value):
        """Validate version follows semantic versioning format if provided"""
        if value:
            version_parts = value.split(".")
            if len(version_parts) != 3:
                raise serializers.ValidationError(
                    "Version must follow semantic versioning format (major.minor.patch), e.g., '1.0.0'"
                )
            try:
                int(version_parts[0])
                int(version_parts[1])
                int(version_parts[2])
            except ValueError:
                raise serializers.ValidationError("Version parts must be numeric (e.g., '1.0.0')")
        return value

    def validate(self, attrs):
        """Cross-field validation"""
        query = attrs.get("query")
        query_type = attrs.get("query_type")

        if query and query_type:
            query_upper = query.upper().strip()

            if query_type == QueryType.SQL:
                if not any(
                    keyword in query_upper
                    for keyword in ["SELECT", "WITH", "INSERT", "UPDATE", "DELETE"]
                ):
                    raise serializers.ValidationError(
                        {
                            "query": "SQL query should contain SQL keywords (SELECT, WITH, INSERT, UPDATE, DELETE)"
                        }
                    )
            elif query_type == QueryType.SPARQL:
                if not any(
                    keyword in query_upper
                    for keyword in ["SELECT", "CONSTRUCT", "ASK", "DESCRIBE", "PREFIX"]
                ):
                    raise serializers.ValidationError(
                        {
                            "query": "SPARQL query should contain SPARQL keywords (SELECT, CONSTRUCT, ASK, DESCRIBE, PREFIX)"
                        }
                    )

        return attrs


class VirtualDatasetValidationResponseSerializer(serializers.Serializer):
    """Serializer for virtual dataset validation response"""

    is_valid = serializers.BooleanField(help_text="Whether validation passed")
    errors = serializers.ListField(
        child=serializers.CharField(), help_text="List of validation errors"
    )
    warnings = serializers.ListField(
        child=serializers.CharField(), help_text="List of validation warnings"
    )
    details = serializers.DictField(help_text="Detailed validation results")


class VirtualDatasetVersionSerializer(serializers.Serializer):
    """Serializer for virtual dataset version information"""

    version = serializers.CharField(help_text="Version string")
    status = serializers.CharField(help_text="Status of this version")
    created_at = serializers.DateTimeField(help_text="When this version was created")
    updated_at = serializers.DateTimeField(help_text="When this version was last updated")
    query_type = serializers.CharField(help_text="Query type for this version")
    source_count = serializers.IntegerField(help_text="Number of sources in this version")


class QueryExecutionSerializer(serializers.ModelSerializer):
    """Serializer for QueryExecution model"""

    virtual_dataset_name = serializers.CharField(
        source="virtual_dataset.name", read_only=True, help_text="Name of the virtual dataset"
    )
    virtual_dataset = serializers.UUIDField(
        source="virtual_dataset.id", read_only=True, help_text="Virtual dataset ID"
    )

    class Meta:
        model = QueryExecution
        fields = [
            "id",
            "virtual_dataset",
            "virtual_dataset_name",
            "query",
            "parameters",
            "execution_mode",
            "status",
            "started_at",
            "completed_at",
            "result_cache_key",
            "result_storage_path",
            "execution_log",
            "metrics",
            "job",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "virtual_dataset",
            "virtual_dataset_name",
            "status",
            "started_at",
            "completed_at",
            "result_cache_key",
            "result_storage_path",
            "execution_log",
            "metrics",
            "job",
            "created_at",
            "updated_at",
        ]


class QueryExecutionCreateSerializer(serializers.Serializer):
    """Serializer for query execution creation with comprehensive validation"""

    parameters = serializers.JSONField(
        required=False, allow_null=True, default=dict, help_text="Query parameters as JSON object"
    )
    execution_mode = serializers.ChoiceField(
        choices=QueryExecutionMode.choices,
        required=False,
        help_text="Execution mode: SYNC, ASYNC, SCHEDULED, MANUAL, AUTOMATED",
    )
    force_async = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Force asynchronous execution even for small queries",
    )
    timeout_seconds = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        max_value=86400,
        help_text="Query timeout in seconds (default: 300 for sync, 3600 for async)",
    )

    def validate_parameters(self, value):
        """Validate parameters is a dictionary"""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Parameters must be a JSON object (dictionary)")
        return value or {}

    def validate_timeout_seconds(self, value):
        """Validate timeout is within acceptable range"""
        if value is not None:
            if value < 1:
                raise serializers.ValidationError("Timeout must be at least 1 second")
            if value > 86400:
                raise serializers.ValidationError("Timeout cannot exceed 86400 seconds (24 hours)")
        return value


class QueryExecutionResultSerializer(serializers.Serializer):
    """Serializer for query execution result"""

    execution_id = serializers.UUIDField(help_text="Query execution ID")
    data = serializers.JSONField(help_text="Result data (list of rows or formatted string)")
    total_count = serializers.IntegerField(help_text="Total number of rows")
    returned_count = serializers.IntegerField(help_text="Number of rows returned in this response")
    format = serializers.CharField(help_text="Output format (json, csv, parquet)")
    content_type = serializers.CharField(help_text="Content type for the response")
    pagination = serializers.DictField(
        required=False, allow_null=True, help_text="Pagination metadata (if applicable)"
    )
    stream_enabled = serializers.BooleanField(help_text="Whether streaming is enabled")
    stream_url = serializers.CharField(
        required=False, allow_null=True, help_text="Streaming URL (if stream_enabled=True)"
    )


class QueryExecutionProgressSerializer(serializers.Serializer):
    """Serializer for query execution progress"""

    execution_id = serializers.UUIDField(help_text="Query execution ID")
    status = serializers.CharField(help_text="Current execution status")
    progress_percentage = serializers.FloatField(
        required=False, allow_null=True, help_text="Progress percentage (0-100) if available"
    )
    started_at = serializers.DateTimeField(
        required=False, allow_null=True, help_text="When execution started"
    )
    completed_at = serializers.DateTimeField(
        required=False, allow_null=True, help_text="When execution completed"
    )
    duration_seconds = serializers.FloatField(
        required=False, allow_null=True, help_text="Execution duration in seconds"
    )
    metrics = serializers.DictField(required=False, allow_null=True, help_text="Execution metrics")
    latest_logs = serializers.ListField(
        required=False,
        allow_null=True,
        child=serializers.DictField(),
        help_text="Latest log entries",
    )


class QueryExecutionCancelResponseSerializer(serializers.Serializer):
    """Serializer for query execution cancel response"""

    execution_id = serializers.UUIDField(help_text="Query execution ID")
    status = serializers.CharField(help_text="New execution status")
    message = serializers.CharField(help_text="Cancellation message")


# Topology Serializers
class VirtualizationHealthMetricsSerializer(serializers.Serializer):
    """Serializer for virtual dataset health metrics"""

    health_score = serializers.IntegerField(help_text="Health score (0-100)")
    total_executions = serializers.IntegerField(help_text="Total number of query executions")
    completed_executions = serializers.IntegerField(help_text="Number of completed executions")
    failed_executions = serializers.IntegerField(help_text="Number of failed executions")
    running_executions = serializers.IntegerField(
        help_text="Number of currently running executions"
    )
    success_rate = serializers.FloatField(
        allow_null=True, help_text="Success rate percentage (0-100)"
    )
    recent_success_rate = serializers.FloatField(
        allow_null=True, help_text="Recent success rate (last 24 hours) percentage (0-100)"
    )
    recent_failed_count = serializers.IntegerField(
        help_text="Number of failed executions in last 24 hours"
    )
    average_duration_ms = serializers.FloatField(
        allow_null=True, help_text="Average execution duration in milliseconds"
    )
    is_active = serializers.BooleanField(help_text="Whether dataset is active")


class VirtualizationTopologyNodeSerializer(serializers.Serializer):
    """Serializer for topology node (virtual dataset)"""

    id = serializers.UUIDField(help_text="Virtual dataset ID")
    name = serializers.CharField(help_text="Dataset name")
    description = serializers.CharField(
        allow_null=True, allow_blank=True, help_text="Dataset description"
    )
    status = serializers.CharField(help_text="Dataset status")
    query_type = serializers.CharField(help_text="Query type")
    version = serializers.CharField(help_text="Dataset version")
    created_by_id = serializers.UUIDField(
        allow_null=True, help_text="User ID who created the dataset"
    )
    created_at = serializers.DateTimeField(allow_null=True, help_text="Dataset creation timestamp")
    updated_at = serializers.DateTimeField(
        allow_null=True, help_text="Dataset last update timestamp"
    )
    health_metrics = VirtualizationHealthMetricsSerializer(
        required=False, allow_null=True, help_text="Health metrics (if include_health_metrics=true)"
    )

    def to_representation(self, instance):
        """Override to exclude health_metrics if it's None"""
        ret = super().to_representation(instance)
        # Remove health_metrics if it's None (not requested)
        if ret.get("health_metrics") is None:
            ret.pop("health_metrics", None)
        return ret


class VirtualizationTopologyEdgeSerializer(serializers.Serializer):
    """Serializer for topology edge (relationship)"""

    source = serializers.UUIDField(help_text="Source dataset ID")
    target = serializers.UUIDField(help_text="Target dataset ID")
    type = serializers.CharField(help_text="Relationship type (e.g., SHARED_SOURCE)")
    weight = serializers.IntegerField(help_text="Relationship weight/strength")
    shared_sources = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_null=True,
        help_text="List of shared source identifiers",
    )


class VirtualizationTopologyMetadataSerializer(serializers.Serializer):
    """Serializer for topology metadata"""

    tenant_id = serializers.UUIDField(help_text="Tenant ID")
    dataset_count = serializers.IntegerField(help_text="Number of datasets")
    relationship_count = serializers.IntegerField(help_text="Number of relationships")
    generated_at = serializers.DateTimeField(help_text="Topology generation timestamp")


class VirtualizationTopologySummarySerializer(serializers.Serializer):
    """Serializer for topology summary statistics"""

    total_datasets = serializers.IntegerField(help_text="Total number of datasets")
    active_datasets = serializers.IntegerField(help_text="Number of active datasets")
    total_relationships = serializers.IntegerField(help_text="Total number of relationships")
    average_health_score = serializers.FloatField(
        allow_null=True, help_text="Average health score across all datasets"
    )


class VirtualizationTopologySerializer(serializers.Serializer):
    """Serializer for full virtualization topology response"""

    nodes = VirtualizationTopologyNodeSerializer(many=True, help_text="List of dataset nodes")
    edges = VirtualizationTopologyEdgeSerializer(
        many=True, help_text="List of dataset relationships"
    )
    metadata = VirtualizationTopologyMetadataSerializer(help_text="Topology metadata")
    summary = VirtualizationTopologySummarySerializer(help_text="Summary statistics")


class DatasetTopologySerializer(serializers.Serializer):
    """Serializer for single dataset topology view"""

    dataset = VirtualizationTopologyNodeSerializer(help_text="Dataset node")
    relationships = VirtualizationTopologyEdgeSerializer(
        many=True, help_text="Relationships for this dataset"
    )
    health_metrics = VirtualizationHealthMetricsSerializer(
        allow_null=True, help_text="Dataset health metrics"
    )
