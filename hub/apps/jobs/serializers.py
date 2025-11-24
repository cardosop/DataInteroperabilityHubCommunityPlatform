"""
Job Serializers
"""
from rest_framework import serializers
from .models import Job, JobType, JobStatus


class JobSerializer(serializers.ModelSerializer):
    """Serializer for Job model"""
    
    class Meta:
        model = Job
        fields = [
            'id',
            'tenant',
            'type',
            'status',
            'resource_type',
            'resource_id',
            'created_by',
            'started_at',
            'completed_at',
            'error_message',
            'result_json',
            'details_json',
            'timeout_seconds',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'tenant',
            'status',
            'started_at',
            'completed_at',
            'error_message',
            'result_json',
            'created_by',
            'created_at',
            'updated_at'
        ]


class JobCreateSerializer(serializers.Serializer):
    """Serializer for job creation"""
    type = serializers.ChoiceField(choices=JobType.choices)
    resource_type = serializers.CharField(max_length=50)
    resource_id = serializers.UUIDField()
    details_json = serializers.DictField(required=False, allow_null=True)


class JobCancelSerializer(serializers.Serializer):
    """Serializer for job cancellation (no fields needed)"""
    pass

