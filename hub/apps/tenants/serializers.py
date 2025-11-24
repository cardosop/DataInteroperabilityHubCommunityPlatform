"""
Tenant Serializers

DRF serializers for Tenant API.
"""
from rest_framework import serializers
from .models import Tenant, TenantStatus, KYCStatus


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

