"""
Dataset Serializers
"""
from rest_framework import serializers
from .models import Dataset


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

