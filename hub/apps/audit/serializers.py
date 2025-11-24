"""
Audit Event Serializers
"""
from rest_framework import serializers
from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    """Serializer for audit events"""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    actor_user_email = serializers.CharField(source='actor_user.email', read_only=True)
    
    class Meta:
        model = AuditEvent
        fields = [
            'id',
            'tenant',
            'tenant_name',
            'actor_user',
            'actor_user_email',
            'resource_type',
            'resource_id',
            'action',
            'result',
            'details_json',
            'timestamp'
        ]
        read_only_fields = fields

