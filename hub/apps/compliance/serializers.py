"""
Compliance Serializers
"""
from rest_framework import serializers
from .models import ComplianceRun, ComplianceRunStatus, RiskLevel


class ComplianceRunSerializer(serializers.ModelSerializer):
    """Serializer for ComplianceRun model"""
    
    class Meta:
        model = ComplianceRun
        fields = [
            'id',
            'tenant',
            'asset',
            'dataset',
            'file',
            'job',
            'regulations',
            'status',
            'overall_status',
            'risk_level',
            'allowed_to_store',
            'detected_categories_json',
            'column_findings_json',
            'regulation_mapping_json',
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
            'risk_level',
            'allowed_to_store',
            'detected_categories_json',
            'column_findings_json',
            'regulation_mapping_json',
            'started_at',
            'completed_at',
            'created_at',
            'updated_at'
        ]


class ComplianceRunCreateSerializer(serializers.Serializer):
    """Serializer for creating a compliance run"""
    asset_id = serializers.UUIDField(required=False, help_text="Asset ID (optional)")
    dataset_id = serializers.UUIDField(required=False, help_text="Dataset ID (optional)")
    file_id = serializers.UUIDField(required=False, help_text="File ID (optional, scan-only)")
    scan_mode = serializers.ChoiceField(
        choices=['internal', 'external'],
        default='internal',
        help_text="Scan mode: 'internal' for stored data, 'external' for scan-only"
    )
    applicable_regulations = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="List of regulations to check (e.g., ['GDPR', 'HIPAA']). If not provided, all regulations are checked."
    )
    
    def validate(self, data):
        """Validate that at least one of asset_id, dataset_id, or file_id is provided"""
        if not data.get('asset_id') and not data.get('dataset_id') and not data.get('file_id'):
            raise serializers.ValidationError(
                "At least one of asset_id, dataset_id, or file_id must be provided"
            )
        return data

