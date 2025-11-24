"""
DQ Serializers
"""
from rest_framework import serializers
from .models import DQRun, DQRunStatus, DQEngine


class DQRunSerializer(serializers.ModelSerializer):
    """Serializer for DQRun model"""
    
    class Meta:
        model = DQRun
        fields = [
            'id',
            'tenant',
            'asset',
            'dataset',
            'file',
            'job',
            'profile_key',
            'engine',
            'status',
            'overall_status',
            'quality_score',
            'checks_json',
            'details_json',
            'started_at',
            'completed_at',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'tenant',
            'job',
            'status',
            'overall_status',
            'quality_score',
            'checks_json',
            'details_json',
            'started_at',
            'completed_at',
            'created_at',
            'updated_at'
        ]


class DQRunCreateSerializer(serializers.Serializer):
    """Serializer for creating a DQ run"""
    asset_id = serializers.UUIDField(required=False, help_text="Asset ID (optional)")
    dataset_id = serializers.UUIDField(required=False, help_text="Dataset ID (optional)")
    file_id = serializers.UUIDField(required=False, help_text="File ID (optional, scan-only)")
    profile_key = serializers.CharField(
        max_length=100,
        required=False,
        help_text="DQ profile key (e.g., intake_basic_gx, intake_basic_soda). Defaults to tenant default or platform default."
    )
    
    def validate(self, data):
        """Validate that at least one of asset_id, dataset_id, or file_id is provided"""
        if not data.get('asset_id') and not data.get('dataset_id') and not data.get('file_id'):
            raise serializers.ValidationError(
                "At least one of asset_id, dataset_id, or file_id must be provided"
            )
        return data

