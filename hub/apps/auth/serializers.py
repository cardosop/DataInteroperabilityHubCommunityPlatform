"""
Authentication Serializers

Serializers for authentication-related requests and responses.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import uuid

from .models import APIKey, RefreshToken
from hub.apps.users.models import UserStatus
import hashlib

User = get_user_model()


def get_user_permissions(user):
    """
    Get all permissions for a user based on their roles.

    This is a simplified implementation that maps roles to permissions.
    In a production system, you might have a more sophisticated permission system.

    Args:
        user: User instance

    Returns:
        List of permission strings (e.g., ['read:assets', 'write:assets'])
    """
    permissions = []

    # Platform admins have all permissions
    if hasattr(user, 'is_platform_admin') and user.is_platform_admin:
        permissions.extend(['read:*', 'write:*', 'admin:*'])
        return permissions

    # Get permissions from roles
    if hasattr(user, 'user_roles'):
        role_names = [ur.role.name for ur in user.user_roles.all()]

        # Map roles to permissions (simplified mapping)
        role_permission_map = {
            'TENANT_ADMIN': ['read:*', 'write:*', 'admin:tenant'],
            'DATA_PROVIDER': ['read:assets', 'write:assets', 'read:contracts', 'write:contracts'],
            'DATA_CONSUMER': ['read:assets', 'read:contracts', 'read:marketplace'],
            'COMPLIANCE_OFFICER': ['read:*', 'write:compliance', 'read:compliance'],
            'AUDITOR': ['read:*'],
            'USER': ['read:assets', 'read:contracts'],
        }

        for role_name in role_names:
            if role_name in role_permission_map:
                permissions.extend(role_permission_map[role_name])

        # Remove duplicates while preserving order
        seen = set()
        unique_permissions = []
        for perm in permissions:
            if perm not in seen:
                seen.add(perm)
                unique_permissions.append(perm)

        return unique_permissions

    # Default permissions for authenticated users
    return ['read:assets', 'read:contracts']


class LoginSerializer(serializers.Serializer):
    """Serializer for login request"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})


class TokenResponseSerializer(serializers.Serializer):
    """Serializer for token response"""
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    token_type = serializers.CharField(default='Bearer')
    expires_in = serializers.IntegerField()


class RefreshTokenSerializer(serializers.Serializer):
    """Serializer for token refresh request"""
    refresh_token = serializers.CharField()


class RefreshTokenResponseSerializer(serializers.Serializer):
    """Serializer for refresh token response (for listing active sessions)"""
    id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    revoked_at = serializers.DateTimeField(allow_null=True)
    is_current = serializers.BooleanField(help_text="Whether this is the current session's refresh token")

    def to_representation(self, instance):
        """Custom representation to include is_current flag"""
        data = super().to_representation(instance)
        # Check if this is the current session's token
        # We'll determine this in the view by comparing token hashes
        return data


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request"""
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation"""
    token = serializers.UUIDField()
    new_password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})


class InvitationAcceptanceSerializer(serializers.Serializer):
    """Serializer for invitation acceptance"""
    token = serializers.UUIDField()
    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})


class APIKeyCreateSerializer(serializers.ModelSerializer):
    """Serializer for API key creation"""
    scopes = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        help_text="List of scopes (e.g., ['assets:read', 'assets:write'])"
    )
    expires_in_days = serializers.IntegerField(
        required=False,
        default=None,
        help_text="Number of days until expiration (null for non-expiring)"
    )

    class Meta:
        model = APIKey
        fields = ['name', 'scopes', 'expires_in_days']

    def create(self, validated_data):
        """Create API key and return the plaintext key"""
        expires_in_days = validated_data.pop('expires_in_days', None)
        tenant = self.context['tenant']
        user = self.context.get('user')

        # Generate API key
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = timezone.now() + timedelta(days=expires_in_days)

        # Create API key object
        api_key = APIKey.objects.create(
            tenant=tenant,
            user=user,
            key_hash=key_hash,
            name=validated_data['name'],
            scopes=validated_data.get('scopes', []),
            expires_at=expires_at
        )

        # Store plaintext key for response (only shown once)
        api_key._plaintext_key = plaintext_key

        return api_key


class APIKeySerializer(serializers.ModelSerializer):
    """Serializer for API key (without sensitive data)"""

    class Meta:
        model = APIKey
        fields = ['id', 'name', 'scopes', 'expires_at', 'last_used_at', 'created_at']
        read_only_fields = ['id', 'last_used_at', 'created_at']


class APIKeyResponseSerializer(serializers.Serializer):
    """Serializer for API key creation response (includes plaintext key)"""
    id = serializers.UUIDField()
    name = serializers.CharField()
    api_key = serializers.CharField(help_text="Plaintext API key (shown only once)")
    scopes = serializers.ListField()
    expires_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class RegisterSerializer(serializers.Serializer):
    """Serializer for user registration request"""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=128,
        style={'input_type': 'password'},
        help_text="Password must be at least 8 characters and contain uppercase, lowercase, and number"
    )
    name = serializers.CharField(
        required=True,
        max_length=255,
        min_length=1,
        help_text="User full name"
    )
    tenant_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Tenant ID for multi-tenant registration (optional)"
    )

    def validate_email(self, value):
        """Validate email is unique"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email address is already registered")
        return value

    def validate_password(self, value):
        """Validate password strength"""
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters")

        has_upper = any(c.isupper() for c in value)
        has_lower = any(c.islower() for c in value)
        has_digit = any(c.isdigit() for c in value)

        if not (has_upper and has_lower and has_digit):
            raise serializers.ValidationError(
                "Password must contain at least one uppercase letter, one lowercase letter, and one number"
            )

        return value

    def validate_tenant_id(self, value):
        """Validate tenant exists if provided"""
        if value is not None:
            from hub.apps.tenants.models import Tenant
            try:
                tenant = Tenant.objects.get(id=value)
                if not tenant.is_active():
                    raise serializers.ValidationError("Tenant is not active")
            except Tenant.DoesNotExist:
                raise serializers.ValidationError("Tenant not found")
        return value


class RegisterResponseSerializer(serializers.Serializer):
    """Serializer for user registration response"""
    id = serializers.UUIDField()
    email = serializers.EmailField()
    name = serializers.CharField()
    tenant_id = serializers.UUIDField(allow_null=True)
    created_at = serializers.DateTimeField()


class CurrentUserSerializer(serializers.Serializer):
    """Serializer for current user information"""
    id = serializers.UUIDField()
    email = serializers.EmailField()
    name = serializers.CharField(allow_null=True)
    tenant_id = serializers.UUIDField(allow_null=True)
    roles = serializers.ListField(child=serializers.CharField())
    permissions = serializers.ListField(child=serializers.CharField())
    created_at = serializers.DateTimeField()
    last_login_at = serializers.DateTimeField(allow_null=True)

