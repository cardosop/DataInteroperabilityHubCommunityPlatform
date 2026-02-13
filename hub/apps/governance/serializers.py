"""
Governance Serializers

Serializers for governance models (AccessRequest, RetentionPolicy, ComplianceReport).
"""
from rest_framework import serializers
from .models import (
    AccessRequest, AccessRequestStatus,
    RetentionPolicy, RetentionPolicyType, RetentionAction,
    ComplianceReport
)


class AccessRequestSerializer(serializers.ModelSerializer):
    """Serializer for AccessRequest"""
    
    class Meta:
        model = AccessRequest
        fields = [
            'id', 'tenant', 'requested_by', 'asset', 'dataset', 'file',
            'reason', 'requested_access_type', 'status',
            'requires_approval', 'approval_workflow', 'current_approval_step',
            'approvers', 'approved_by', 'approved_at',
            'rejected_by', 'rejected_at', 'rejection_reason',
            'expires_at', 'access_granted_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'requested_by', 'created_at', 'updated_at',
            'approved_by', 'approved_at', 'rejected_by', 'rejected_at',
            'access_granted_at'
        ]


class RetentionPolicySerializer(serializers.ModelSerializer):
    """Serializer for RetentionPolicy"""

    def validate_retention_period_days(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "retention_period_days must be >= 0."
            )
        return value

    def validate_grace_period_days(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "grace_period_days must be >= 0."
            )
        return value

    class Meta:
        model = RetentionPolicy
        fields = [
            'id', 'tenant', 'name', 'description',
            'asset', 'dataset', 'file',
            'policy_type', 'retention_period_days', 'event_trigger',
            'action', 'grace_period_days',
            'legal_hold', 'legal_hold_reason', 'legal_hold_expires_at',
            'enabled', 'last_enforced_at',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'created_by', 'created_at', 'updated_at',
            'last_enforced_at'
        ]


class ComplianceReportSerializer(serializers.ModelSerializer):
    """Serializer for ComplianceReport"""
    
    class Meta:
        model = ComplianceReport
        fields = [
            'id', 'tenant', 'regulation', 'report_type',
            'report_data', 'start_date', 'end_date',
            'scheduled', 'schedule_frequency',
            'email_recipients', 'email_sent', 'email_sent_at',
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'created_by', 'created_at', 'updated_at',
            'email_sent', 'email_sent_at'
        ]

