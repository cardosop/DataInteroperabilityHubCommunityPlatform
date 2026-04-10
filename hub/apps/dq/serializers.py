"""
DQ Serializers
"""
from rest_framework import serializers
from .models import DQAlertingRule, DQRun, DQRunStatus, DQEngine


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
    
    def validate_profile_key(self, value):
        """Validate that profile_key is a valid DQ profile if provided"""
        if value:
            from hub.apps.tenants.validators import VALID_DQ_PROFILES
            if value not in VALID_DQ_PROFILES:
                raise serializers.ValidationError(
                    f"Invalid DQ profile key: {value}. Valid profiles are: {', '.join(VALID_DQ_PROFILES)}"
                )
        return value
    
    def validate(self, data):
        """At least one of asset_id, dataset_id, file_id is validated by DQBusinessRules in service."""
        return data


class DQAlertingRuleSerializer(serializers.ModelSerializer):
    """Serializer for DQAlertingRule model (read)"""

    asset_id = serializers.UUIDField(source="asset.id", read_only=True, allow_null=True)

    class Meta:
        model = DQAlertingRule
        fields = [
            "id",
            "tenant",
            "asset_id",
            "name",
            "description",
            "metric_type",
            "threshold",
            "comparison_operator",
            "severity",
            "alert_channels",
            "enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "created_at",
            "updated_at",
        ]


class DQAlertingRuleCreateSerializer(serializers.Serializer):
    """Serializer for creating / updating a DQ alerting rule"""

    asset_id = serializers.UUIDField(required=True, help_text="Asset ID to attach the rule to")
    name = serializers.CharField(max_length=255, required=False, default="Quality Score Alert")
    description = serializers.CharField(required=False, allow_blank=True, default="")
    metric_type = serializers.CharField(max_length=100, required=False, default="quality_score")
    threshold = serializers.FloatField(required=True, help_text="Threshold value")
    comparison_operator = serializers.ChoiceField(
        choices=["<", "<=", ">", ">=", "==", "!="],
        required=False,
        default="<",
    )
    severity = serializers.ChoiceField(
        choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        required=False,
        default="MEDIUM",
    )
    alert_channels = serializers.ListField(
        child=serializers.ChoiceField(choices=["EMAIL", "SLACK", "WEBHOOK", "PAGERDUTY"]),
        required=False,
        default=["EMAIL"],
    )
    channel_config = serializers.DictField(required=False, default=dict)
    enabled = serializers.BooleanField(required=False, default=True)

