"""
Observability Serializers
"""
from rest_framework import serializers
from .models import DataObservabilityMetric, VolumeTrend, SchemaDrift


class FreshnessMetricSerializer(serializers.ModelSerializer):
    """Serializer for freshness metrics"""
    class Meta:
        model = DataObservabilityMetric
        fields = [
            'id',
            'dataset_id',
            'asset_id',
            'last_update_time',
            'freshness_age_seconds',
            'freshness_sla',
            'freshness_sla_seconds',
            'is_stale',
            'recorded_at'
        ]
        read_only_fields = ['id', 'recorded_at']


class FreshnessDashboardSerializer(serializers.Serializer):
    """Serializer for freshness dashboard"""
    results = FreshnessMetricSerializer(many=True)
    summary = serializers.DictField()


class VolumeTrendSerializer(serializers.ModelSerializer):
    """Serializer for volume trends"""
    class Meta:
        model = VolumeTrend
        fields = [
            'id',
            'dataset_id',
            'asset_id',
            'period_start',
            'period_end',
            'period_type',
            'avg_row_count',
            'min_row_count',
            'max_row_count',
            'avg_size_bytes',
            'min_size_bytes',
            'max_size_bytes',
            'sample_count',
            'is_anomaly',
            'anomaly_type',
            'anomaly_score',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class VolumeDashboardSerializer(serializers.Serializer):
    """Serializer for volume dashboard"""
    results = VolumeTrendSerializer(many=True)
    summary = serializers.DictField()


class SchemaDriftSerializer(serializers.ModelSerializer):
    """Serializer for schema drifts"""
    class Meta:
        model = SchemaDrift
        fields = [
            'id',
            'dataset_id',
            'asset_id',
            'previous_schema_hash',
            'current_schema_hash',
            'new_fields',
            'removed_fields',
            'type_changes',
            'nullable_changes',
            'drift_severity',
            'tolerance_config',
            'is_within_tolerance',
            'detected_at'
        ]
        read_only_fields = ['id', 'detected_at']


class SchemaDriftDashboardSerializer(serializers.Serializer):
    """Serializer for schema drift dashboard"""
    results = SchemaDriftSerializer(many=True)
    summary = serializers.DictField()

