"""
Dataset Serializers
"""
from rest_framework import serializers
from .models import Dataset, SchemaVersion
# Phase 226 G7a — canonical IRI exposure for SDK + dereferenceability proofs.
from hub.apps.semantic.iri import canonical_iri_for


class DatasetSerializer(serializers.ModelSerializer):
    """
    Serializer for Dataset model. UUID FKs are serialized as strings for JSON consistency.

    Writable fields on update: asset, format (others are read-only).
    name: Read-only, computed from instance.file.name (not persisted).
    description: Not supported; Dataset model has no description field (not persisted).
    """

    canonical_iri = serializers.SerializerMethodField(
        help_text=(
            "Canonical Linked Data IRI: {SEMANTIC_BASE_IRI}/id/dataset/{id}. "
            "Stable identifier for JSON-LD dereference. See Phase 226 G7a."
        )
    )

    def get_canonical_iri(self, obj) -> str:
        return canonical_iri_for("dataset", obj.id)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Ensure UUID FKs are strings in API response (JSON has no native UUID type)
        for key in ("id", "tenant", "asset", "file", "parent_version", "created_by"):
            if key in data and data[key] is not None:
                data[key] = str(data[key])
        # Add computed name and size_bytes for frontend (Dataset has no name field)
        data["name"] = instance.file.name if instance.file else str(instance)
        data["size_bytes"] = instance.file.size if instance.file else 0
        # Add asset_id and asset_name for frontend (asset is FK UUID; asset_name for list UX)
        if instance.asset_id:
            data["asset_id"] = str(instance.asset_id)
            try:
                data["asset_name"] = instance.asset.name
            except Exception:
                data["asset_name"] = None
        return data

    class Meta:
        model = Dataset
        fields = [
            'id',
            'tenant',
            'asset',
            'file',
            'schema_json',
            'sample_data_json',
            'row_count',
            'format',
            'version',
            'parent_version',
            'semantic_version',
            'version_tags',
            'is_current',
            'status',
            'retired_at',
            'kind',
            'file_handle_purpose',
            'created_by',
            'created_at',
            'updated_at',
            'canonical_iri',
        ]
        read_only_fields = [
            'id',
            'tenant',
            'schema_json',
            'sample_data_json',
            'row_count',
            'version',
            'parent_version',
            'semantic_version',
            'version_tags',
            'is_current',
            'status',
            'retired_at',
            'kind',
            'file_handle_purpose',
            'created_by',
            'created_at',
            'updated_at',
            'canonical_iri',
        ]


class DatasetCreateSerializer(serializers.Serializer):
    """Serializer for dataset creation"""
    file_id = serializers.UUIDField(help_text="ID of the file to create dataset from")
    asset_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="ID of the asset to attach dataset to (optional)"
    )
    kind = serializers.ChoiceField(
        choices=[
            ("FILE", "File-based dataset"),
            ("EXTERNAL_REF", "External reference dataset"),
        ],
        default="FILE",
        help_text="Dataset kind. Only FILE is settable via API; "
                  "EXTERNAL_REF is set server-side by the federation pipeline.",
    )
    file_handle_purpose = serializers.ChoiceField(
        choices=[
            ("PRIMARY", "Primary"),
            ("SAMPLE", "Sample"),
            ("SCHEMA_ONLY", "Schema Only"),
        ],
        required=False,
        help_text="Purpose for which the file handle was stored (e.g. primary, sample, schema_only)"
    )

    def validate_kind(self, value):
        """Block external clients from creating EXTERNAL_REF datasets.

        Per OQ260.3: only FILE-kind datasets are settable via the API.
        EXTERNAL_REF is written server-side by the federation pipeline.
        """
        if value == "EXTERNAL_REF":
            raise serializers.ValidationError(
                "EXTERNAL_REF datasets cannot be created via the API. "
                "They are set server-side by the federation pipeline.",
                code="EXTERNAL_REF_NOT_API_SETTABLE",
            )
        return value


class DatasetVersionCreateSerializer(serializers.Serializer):
    """Serializer for creating a new dataset version"""
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Description of changes in this version"
    )
    schema_changes = serializers.DictField(
        required=False,
        help_text="Schema changes summary (added_fields, removed_fields, modified_fields)"
    )
    semantic_version = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Semantic version string (e.g., '1.0.0'). If not provided, will be inferred."
    )
    version_tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Version tags (e.g., ['production', 'staging'])"
    )


class DatasetVersionSerializer(serializers.ModelSerializer):
    """Serializer for Dataset version listing"""
    parent_version_id = serializers.UUIDField(source='parent_version.id', read_only=True, allow_null=True)
    schema_version_id = serializers.UUIDField(source='schema_version.id', read_only=True, allow_null=True)
    compatibility_level = serializers.CharField(source='schema_version.compatibility_level', read_only=True, allow_null=True)
    
    class Meta:
        model = Dataset
        fields = [
            'id',
            'version',
            'semantic_version',
            'version_tags',
            'is_current',
            'parent_version_id',
            'schema_version_id',
            'compatibility_level',
            'schema_json',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'version',
            'semantic_version',
            'version_tags',
            'is_current',
            'parent_version_id',
            'schema_version_id',
            'compatibility_level',
            'schema_json',
            'created_at',
            'updated_at'
        ]


class SchemaVersionCompareSerializer(serializers.Serializer):
    """Serializer for schema version comparison request"""
    version1 = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="First version ID (defaults to parent version if not provided)"
    )
    version2 = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Second version ID (defaults to current version if not provided)"
    )


class DatasetRefreshFromFileSerializer(serializers.Serializer):
    """Request serializer for refreshing a dataset from its source file."""
    file_id = serializers.UUIDField(required=True)


class DatasetRefreshFromFileResponseSerializer(serializers.Serializer):
    """Response serializer for dataset refresh operation."""
    pass


class DatasetManualRefreshResponseSerializer(serializers.Serializer):
    """Response serializer for manual dataset refresh."""
    pass

