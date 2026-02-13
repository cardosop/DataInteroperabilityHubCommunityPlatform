"""
Authentication Models

API Keys and Refresh Tokens for authentication.
"""
import uuid
import hashlib
import secrets
from django.db import models
from django.utils import timezone
from django.conf import settings


class APIKey(models.Model):
    """
    API Key model for programmatic access.
    
    API keys are hashed before storage and can have scopes for fine-grained access control.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="api_keys",
        help_text="Tenant this API key belongs to"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
        null=True,
        blank=True,
        help_text="User this API key belongs to (optional, for user-scoped keys)"
    )
    key_hash = models.CharField(
        max_length=128,
        unique=True,
        help_text="SHA-256 hash of the API key (stored, not plaintext)"
    )
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for the API key"
    )
    scopes = models.JSONField(
        default=list,
        help_text="List of scopes (e.g., ['assets:read', 'assets:write'])"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Expiration timestamp (null for non-expiring keys)"
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this API key was used"
    )
    rate_limit_per_hour = models.IntegerField(
        null=True,
        blank=True,
        help_text="Custom API gateway rate limit (requests per hour); null uses tier/tenant default"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "api_keys"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "user"]),
            models.Index(fields=["key_hash"]),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
    
    @staticmethod
    def generate_key() -> str:
        """Generate a new API key (random string)"""
        return secrets.token_urlsafe(32)  # 32 bytes = 43 characters base64url
    
    @staticmethod
    def hash_key(key: str) -> str:
        """Hash an API key using SHA-256"""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def is_expired(self) -> bool:
        """Check if API key is expired"""
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at
    
    def update_last_used(self):
        """Update last_used_at timestamp"""
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])


class RefreshToken(models.Model):
    """
    Refresh Token model for JWT refresh flow.
    
    Refresh tokens are stored hashed and can be revoked.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="refresh_tokens",
        help_text="User this refresh token belongs to"
    )
    token_hash = models.CharField(
        max_length=128,
        unique=True,
        help_text="SHA-256 hash of the refresh token (stored, not plaintext)"
    )
    expires_at = models.DateTimeField(
        help_text="Expiration timestamp"
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this token was revoked (null if active)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "refresh_tokens"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "revoked_at"]),
            models.Index(fields=["token_hash"]),
            models.Index(fields=["expires_at"]),
        ]
    
    def __str__(self):
        return f"RefreshToken for {self.user.email} (expires: {self.expires_at})"
    
    @staticmethod
    def generate_token() -> str:
        """Generate a new refresh token (random string)"""
        return secrets.token_urlsafe(32)  # 32 bytes = 43 characters base64url
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a refresh token using SHA-256"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def is_expired(self) -> bool:
        """Check if refresh token is expired"""
        return timezone.now() > self.expires_at
    
    def is_revoked(self) -> bool:
        """Check if refresh token is revoked"""
        return self.revoked_at is not None
    
    def is_valid(self) -> bool:
        """Check if refresh token is valid (not expired and not revoked)"""
        return not self.is_expired() and not self.is_revoked()
    
    def revoke(self):
        """Revoke this refresh token"""
        if not self.revoked_at:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at", "updated_at"])

