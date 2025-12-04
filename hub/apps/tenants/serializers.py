"""
Tenant Serializers

DRF serializers for Tenant API.
"""
from rest_framework import serializers
from .models import Tenant, TenantStatus, KYCStatus, TenantConfig
from .validators import (
    validate_dq_profile,
    validate_compliance_regimes,
    validate_rate_limits,
    get_platform_defaults,
)


class TenantSerializer(serializers.ModelSerializer):
    """Serializer for Tenant model"""
    
    status = serializers.ChoiceField(choices=TenantStatus.choices, read_only=True)
    kyc_status = serializers.ChoiceField(choices=KYCStatus.choices)
    
    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "slug",
            "status",
            "kyc_status",
            "region",
            "deleted_at",
            "created_at",
            "updated_at"
        ]
        read_only_fields = ["id", "status", "deleted_at", "created_at", "updated_at"]
    
    def validate_slug(self, value):
        """Validate slug format"""
        if not value.replace("-", "").replace("_", "").isalnum():
            raise serializers.ValidationError(
                "Slug must contain only lowercase letters, numbers, and hyphens."
            )
        return value.lower()


class TenantCreateSerializer(serializers.ModelSerializer):
    """Serializer for tenant creation"""
    
    class Meta:
        model = Tenant
        fields = ["name", "slug", "region"]
    
    def validate_slug(self, value):
        """Validate and normalize slug"""
        if not value.replace("-", "").replace("_", "").isalnum():
            raise serializers.ValidationError(
                "Slug must contain only lowercase letters, numbers, and hyphens."
            )
        return value.lower()
    
    def create(self, validated_data):
        """Create tenant with default status"""
        tenant = Tenant.objects.create(
            name=validated_data["name"],
            slug=validated_data["slug"],
            region=validated_data.get("region"),
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED
        )
        return tenant


class TenantUpdateSerializer(serializers.ModelSerializer):
    """Serializer for tenant update"""
    
    class Meta:
        model = Tenant
        fields = ["name", "slug", "kyc_status", "region"]
    
    def validate_slug(self, value):
        """Validate and normalize slug"""
        if not value.replace("-", "").replace("_", "").isalnum():
            raise serializers.ValidationError(
                "Slug must contain only lowercase letters, numbers, and hyphens."
            )
        return value.lower()


class TenantSuspendSerializer(serializers.Serializer):
    """Serializer for tenant suspension"""
    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional reason for suspension"
    )


class TenantReactivateSerializer(serializers.Serializer):
    """Serializer for tenant reactivation"""
    pass


class RateLimitsSerializer(serializers.Serializer):
    """Serializer for rate limits structure"""
    
    burst_per_10s = serializers.IntegerField(required=False, min_value=1)
    sustained_per_min = serializers.IntegerField(required=False, min_value=1)
    daily_cap = serializers.IntegerField(required=False, min_value=1)
    
    def validate(self, data):
        """Validate rate limits structure"""
        # At least one limit must be specified
        if not any(key in data for key in ['burst_per_10s', 'sustained_per_min', 'daily_cap']):
            raise serializers.ValidationError(
                "At least one rate limit (burst_per_10s, sustained_per_min, or daily_cap) must be specified"
            )
        return data


class TenantConfigSerializer(serializers.ModelSerializer):
    """Serializer for TenantConfig model"""
    
    tenant_id = serializers.UUIDField(source='tenant.id', read_only=True)
    rate_limits = serializers.DictField(
        child=RateLimitsSerializer(),
        required=False,
        allow_null=True,
        help_text="Per-endpoint category rate limits"
    )
    
    class Meta:
        model = TenantConfig
        fields = [
            "tenant_id",
            "default_dq_profile",
            "allowed_compliance_regimes",
            "default_compliance_regimes",
            "data_retention_days",
            "rate_limits",
            "max_file_size_bytes",
            "max_job_concurrency",
            "max_queued_jobs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["tenant_id", "created_at", "updated_at"]
    
    def validate_default_dq_profile(self, value):
        """Validate DQ profile"""
        if value:
            validate_dq_profile(value)
        return value
    
    def validate_allowed_compliance_regimes(self, value):
        """Validate allowed compliance regimes"""
        if value:
            validate_compliance_regimes(value)
        return value
    
    def validate_default_compliance_regimes(self, value):
        """Validate default compliance regimes"""
        if value:
            validate_compliance_regimes(value)
        return value
    
    def validate_rate_limits(self, value):
        """Validate rate limits"""
        if value:
            validate_rate_limits(value)
        return value
    
    def validate(self, data):
        """Validate cross-field constraints"""
        # Validate default_compliance_regimes is subset of allowed_compliance_regimes
        allowed = data.get('allowed_compliance_regimes') or []
        default = data.get('default_compliance_regimes') or []
        
        # If updating, get existing values from instance
        if self.instance:
            allowed = data.get('allowed_compliance_regimes', self.instance.allowed_compliance_regimes or [])
            default = data.get('default_compliance_regimes', self.instance.default_compliance_regimes or [])
        
        if default and allowed:
            default_set = set(default)
            allowed_set = set(allowed)
            if not default_set.issubset(allowed_set):
                raise serializers.ValidationError({
                    'default_compliance_regimes': 'Default compliance regimes must be a subset of allowed compliance regimes.'
                })
        
        return data


class TenantConfigUpdateSerializer(serializers.ModelSerializer):
    """Serializer for partial TenantConfig updates"""
    
    rate_limits = serializers.DictField(
        child=RateLimitsSerializer(),
        required=False,
        allow_null=True,
        help_text="Per-endpoint category rate limits"
    )
    
    class Meta:
        model = TenantConfig
        fields = [
            "default_dq_profile",
            "allowed_compliance_regimes",
            "default_compliance_regimes",
            "data_retention_days",
            "rate_limits",
            "max_file_size_bytes",
            "max_job_concurrency",
            "max_queued_jobs",
        ]
    
    def validate_default_dq_profile(self, value):
        """Validate DQ profile"""
        if value:
            validate_dq_profile(value)
        return value
    
    def validate_allowed_compliance_regimes(self, value):
        """Validate allowed compliance regimes"""
        if value:
            validate_compliance_regimes(value)
        return value
    
    def validate_default_compliance_regimes(self, value):
        """Validate default compliance regimes"""
        if value:
            validate_compliance_regimes(value)
        return value
    
    def validate_rate_limits(self, value):
        """Validate rate limits"""
        if value:
            validate_rate_limits(value)
        return value
    
    def validate(self, data):
        """Validate cross-field constraints"""
        # Get existing values from instance
        allowed = data.get('allowed_compliance_regimes', self.instance.allowed_compliance_regimes if self.instance else [])
        default = data.get('default_compliance_regimes', self.instance.default_compliance_regimes if self.instance else [])
        
        if default and allowed:
            default_set = set(default)
            allowed_set = set(allowed)
            if not default_set.issubset(allowed_set):
                raise serializers.ValidationError({
                    'default_compliance_regimes': 'Default compliance regimes must be a subset of allowed compliance regimes.'
                })
        
        return data

