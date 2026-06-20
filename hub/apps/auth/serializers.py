"""
Authentication Serializers

Serializers for authentication-related requests and responses.
"""

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import APIKey

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
    if hasattr(user, "is_platform_admin") and user.is_platform_admin:
        permissions.extend(["read:*", "write:*", "admin:*", "VIEW_PII"])
        return permissions

    # Get permissions from roles
    if hasattr(user, "user_roles"):
        role_names = [ur.role.name for ur in user.user_roles.all()]

        # Map roles to permissions (simplified mapping)
        role_permission_map = {
            "TENANT_ADMIN": ["read:*", "write:*", "admin:tenant"],
            "DATA_PROVIDER": ["read:assets", "write:assets", "read:contracts", "write:contracts"],
            "DATA_CONSUMER": ["read:assets", "read:contracts", "read:marketplace"],
            "DATA_VIEWER": ["read:assets", "read:contracts"],
            "PII_VIEWER": ["VIEW_PII", "read:assets", "read:contracts"],
            "COMPLIANCE_OFFICER": ["read:*", "write:compliance", "read:compliance"],
            "AUDITOR": ["read:*"],
            "USER": ["read:assets", "read:contracts"],
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
    return ["read:assets", "read:contracts"]


class LoginSerializer(serializers.Serializer):
    """Serializer for login request"""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class TokenResponseSerializer(serializers.Serializer):
    """Serializer for token response (11.1: refresh_token omitted — delivered via httpOnly cookie)"""

    access_token = serializers.CharField()
    refresh_token = serializers.CharField(required=False, allow_null=True)
    token_type = serializers.CharField(default="Bearer")
    expires_in = serializers.IntegerField()


class RefreshTokenSerializer(serializers.Serializer):
    """Serializer for token refresh request (11.1: token may arrive via cookie, body optional)"""

    refresh_token = serializers.CharField(required=False, allow_blank=True, default="")


class RefreshTokenResponseSerializer(serializers.Serializer):
    """Serializer for refresh token response (for listing active sessions)"""

    id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    revoked_at = serializers.DateTimeField(allow_null=True)
    is_current = serializers.BooleanField(
        help_text="Whether this is the current session's refresh token"
    )

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
    """Serializer for password reset confirmation (11.3: token is plaintext UUID string)"""

    token = serializers.CharField(max_length=64)
    new_password = serializers.CharField(
        write_only=True, min_length=10, style={"input_type": "password"}
    )


class InvitationAcceptanceSerializer(serializers.Serializer):
    """Serializer for invitation acceptance (11.3: token is plaintext UUID string)"""

    token = serializers.CharField(max_length=64)
    password = serializers.CharField(
        write_only=True, min_length=10, style={"input_type": "password"}
    )


class EmailVerificationSerializer(serializers.Serializer):
    """POST /auth/verify-email/ — Phase 204 signed token from email link."""

    token = serializers.CharField(max_length=512)


class ResendEmailVerificationSerializer(serializers.Serializer):
    """POST /auth/resend-verification/ — rate-limited per email."""

    email = serializers.EmailField()


class APIKeyCreateSerializer(serializers.ModelSerializer):
    """Serializer for API key creation"""

    scopes = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        help_text="List of scopes (e.g., ['assets:read', 'assets:write'])",
    )
    expires_in_days = serializers.IntegerField(
        required=False,
        default=None,
        help_text="Number of days until expiration (null for non-expiring)",
    )

    class Meta:
        model = APIKey
        fields = ["name", "scopes", "expires_in_days"]

    def create(self, validated_data):
        """Create API key and return the plaintext key"""
        expires_in_days = validated_data.pop("expires_in_days", None)
        tenant = self.context["tenant"]
        user = self.context.get("user")

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
            name=validated_data["name"],
            scopes=validated_data.get("scopes", []),
            expires_at=expires_at,
        )

        # Store plaintext key for response (only shown once)
        api_key._plaintext_key = plaintext_key

        return api_key


class APIKeySerializer(serializers.ModelSerializer):
    """Serializer for API key (without sensitive data)"""

    class Meta:
        model = APIKey
        fields = ["id", "name", "scopes", "expires_at", "last_used_at", "created_at"]
        read_only_fields = ["id", "last_used_at", "created_at"]


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
        min_length=10,
        max_length=128,
        style={"input_type": "password"},
        help_text="Password must be at least 8 characters and contain uppercase, lowercase, and number",
    )
    name = serializers.CharField(
        required=True, max_length=255, min_length=1, help_text="User full name"
    )
    tenant_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Tenant ID for multi-tenant registration (optional)",
    )
    signup_consent = serializers.BooleanField(
        required=False,
        default=False,
        help_text=(
            "Must be true when registering into a tenant with "
            "compliance_consent_enabled and configured signup.privacy purpose."
        ),
    )

    def validate_password(self, value):
        """Validate password strength via Django's configured validators + inline checks.

        Phase 277.B.065 — delegates to ``django.contrib.auth.password_validation``
        which runs all configured ``AUTH_PASSWORD_VALIDATORS`` including the
        custom complexity, deny-list, and HIBP validators.
        """
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError

        # Fast inline check first (avoids validator overhead for trivially weak passwords)
        if len(value) < 10:
            raise serializers.ValidationError("Password must be at least 10 characters")

        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages) from e

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
    avatar = serializers.URLField(allow_null=True, required=False)
    preferences = serializers.JSONField(required=False)
    feature_tenant_switch_enabled = serializers.BooleanField(
        required=False,
        default=True,
        help_text="When false, tenant switch UI and X-Tenant-Id are disabled.",
    )


class MePatchSerializer(serializers.Serializer):
    """Serializer for PATCH /auth/me/ — partial profile update"""

    display_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="User display name",
    )
    avatar = serializers.URLField(
        max_length=500,
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="URL to user avatar image",
    )
    preferences = serializers.JSONField(
        required=False, help_text="User preferences (theme, language, notifications, etc.)"
    )
    # Phase 278.E.3 — saved list filters/views
    saved_views = serializers.JSONField(
        required=False,
        help_text="Saved list views [{resource_type, name, filters, sort}]",
    )

    def validate_display_name(self, value):
        if value is not None and len(value.strip()) == 0:
            return None
        return value.strip() if value else value

    def validate_preferences(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Preferences must be a JSON object")
        try:
            serialized = json.dumps(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError("Preferences must be JSON-serializable")
        if len(serialized) > 10240:
            raise serializers.ValidationError("Preferences must be at most 10KB when serialized")
        return value
