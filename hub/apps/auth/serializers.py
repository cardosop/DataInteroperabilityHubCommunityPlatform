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

User = get_user_model()


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

