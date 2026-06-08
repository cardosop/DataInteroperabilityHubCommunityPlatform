"""
Authentication Models

API Keys and Refresh Tokens for authentication.
"""
import uuid
import hashlib
import secrets
from datetime import timedelta
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
    # BaaS: optional tier for usage/quota (single API key model — D2)
    tier = models.ForeignKey(
        "baas.APITierModel",
        on_delete=models.RESTRICT,
        related_name="auth_api_keys",
        null=True,
        blank=True,
        help_text="BaaS API tier for this key (null for non-BaaS keys)"
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Revocation timestamp (null if active); used for BaaS revoke"
    )
    # Customer billing fields (Phase 116A.1)
    customer_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="External customer identifier for billing"
    )
    customer_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Customer display name for billing reports"
    )
    customer_email = models.EmailField(
        null=True,
        blank=True,
        help_text="Customer billing email address"
    )
    customer_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional customer metadata (plan, region, etc.)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    

    last_rotation_reminder_at = models.DateTimeField(null=True, blank=True, help_text="Last rotation reminder timestamp")
    class Meta:
        db_table = "api_keys"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "user"]),
            models.Index(fields=["key_hash"]),
            models.Index(fields=["tier_id"]),
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

    def is_revoked(self) -> bool:
        """Check if API key is revoked (BaaS-style revocation)"""
        return self.revoked_at is not None

    def is_active(self) -> bool:
        """Check if API key is active (not revoked and not expired)"""
        if self.revoked_at is not None:
            return False
        return not self.is_expired()

    def revoke(self):
        """Revoke this API key (sets revoked_at)."""
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at", "updated_at"])

    def update_last_used(self):
        """Update last_used_at timestamp"""
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])

    def verify_key(self, key: str) -> bool:
        """Verify if a plaintext key matches this API key's hash (BaaS compatibility)."""
        return self.key_hash == self.hash_key(key)


class RefreshToken(models.Model):
    """
    Refresh Token model for JWT refresh flow.

    Refresh tokens are stored hashed and participate in family rotation: every
    use issues a new sibling token with the same family_id and an incremented
    sequence_number.  If a revoked token is presented (replay / theft) the
    entire family is revoked and the user must re-authenticate.
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
    # --- family rotation (11.2) ---
    family_id = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        help_text="Shared UUID for all tokens in one rotation chain"
    )
    sequence_number = models.IntegerField(
        default=0,
        help_text="Monotonically increasing within a family; 0 = first issue"
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

    tenant_id = models.UUIDField(null=True, blank=True, help_text="Tenant ID associated with this refresh token")
    class Meta:
        db_table = "refresh_tokens"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "revoked_at"]),
            models.Index(fields=["token_hash"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["family_id"]),
        ]

    def save(self, *args, **kwargs):
        """Enforce maximum refresh token lifetime (Phase 90)."""
        from django.conf import settings as django_settings
        max_days = getattr(
            django_settings, "REFRESH_TOKEN_MAX_LIFETIME_DAYS", 30
        )
        max_expiry = timezone.now() + timedelta(days=max_days)
        if self.expires_at is None:
            self.expires_at = max_expiry
        elif self.expires_at > max_expiry:
            self.expires_at = max_expiry
        super().save(*args, **kwargs)

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

    def revoke_family(self):
        """Revoke all tokens in this family (theft / replay detected)."""
        RefreshToken.objects.filter(
            family_id=self.family_id, revoked_at__isnull=True
        ).update(revoked_at=timezone.now())


class LoginAttempt(models.Model):
    """
    Records each login attempt for account-level lockout (11.5).

    Successful logins are recorded so that a sudden burst of failures after
    long-standing success can trigger enhanced monitoring in future.
    """
    email = models.EmailField(
        db_index=True,
        help_text="Email address used in the attempt"
    )
    ip_address = models.GenericIPAddressField(
        help_text="Client IP address"
    )
    success = models.BooleanField(
        default=False,
        help_text="True if the attempt resulted in a successful login"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "login_attempts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
        ]

    def __str__(self):
        status = "OK" if self.success else "FAIL"
        return f"LoginAttempt {status} {self.email} from {self.ip_address}"

