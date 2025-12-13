"""
Dataset Serializers
"""
from rest_framework import serializers
from .models import Dataset, SchemaVersion


class DatasetSerializer(serializers.ModelSerializer):
    """Serializer for Dataset model"""
    
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
            'created_by',
            'created_at',
            'updated_at'
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
            'created_by',
            'created_at',
            'updated_at'
        ]


class DatasetCreateSerializer(serializers.Serializer):
    """Serializer for dataset creation"""
    file_id = serializers.UUIDField(help_text="ID of the file to create dataset from")
    asset_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="ID of the asset to attach dataset to (optional)"
    )


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

