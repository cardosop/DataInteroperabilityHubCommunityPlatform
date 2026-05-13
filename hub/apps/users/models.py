"""
User Management Models

Defines User and Role models with relationships.
"""
import uuid
import weakref

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import EmailValidator
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

# Registry of live User Python objects keyed by PK, so signal handlers can
# find and clear the per-instance _role_cache on the exact object held by the
# caller — without performing an extra DB query.  WeakValueDictionary ensures
# User objects that have gone out of scope are not kept alive by this registry.
_live_user_instances: weakref.WeakValueDictionary = weakref.WeakValueDictionary()


class UserStatus(models.TextChoices):
    """User status enumeration"""
    ACTIVE = "ACTIVE", "Active"
    INVITED = "INVITED", "Invited"
    DISABLED = "DISABLED", "Disabled"
    SUSPENDED = "SUSPENDED", "Suspended"


class UserManager(BaseUserManager):
    """Custom user manager"""
    
    def create_user(self, email, password=None, tenant=None, **extra_fields):
        """Create and save a regular user"""
        if not email:
            raise ValueError("The Email field must be set")
        
        email = self.normalize_email(email)
        user = self.model(email=email, tenant=tenant, **extra_fields)
        
        if password:
            user.set_password(password)
        
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, tenant=None, **extra_fields):
        """Create and save a superuser (platform admin)"""
        extra_fields.setdefault("is_platform_admin", True)
        extra_fields.setdefault("status", UserStatus.ACTIVE)
        
        if extra_fields.get("is_platform_admin") is not True:
            raise ValueError("Superuser must have is_platform_admin=True")

        extra_fields.setdefault("email_verified", True)

        return self.create_user(email, password, tenant, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model representing a user account.
    
    Each user belongs to exactly one tenant (except platform admins).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.RESTRICT,
        related_name="users",
        null=True,
        blank=True,
        help_text="Tenant this user belongs to (null for platform admins)"
    )
    email = models.EmailField(
        unique=True,
        validators=[EmailValidator()],
        help_text="User email address (unique across platform)"
    )
    display_name = models.CharField(
        max_length=255,
        default="",  # Phase 92: empty string instead of NULL
        blank=True,
        help_text="User display name"
    )
    avatar_url = models.URLField(
        max_length=500,
        default="",  # Phase 92: empty string instead of NULL
        blank=True,
        help_text="URL to user avatar image (e.g. gravatar, CDN)"
    )
    preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="User preferences (theme, language, notifications, etc.)"
    )
    # Phase 278.E.3 — saved list filters/views per user. Each entry:
    # {resource_type: string, name: string, filters: dict, sort: string}
    # URL-shareable via the view's ?saved=<name> query param.
    saved_views = models.JSONField(
        default=list,
        blank=True,
        help_text="Saved list filters/views (URL-shareable).",
    )
    status = models.CharField(
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.INVITED,
        help_text="User status: ACTIVE, INVITED, or DISABLED"
    )
    is_platform_admin = models.BooleanField(
        default=False,
        help_text="Platform-level admin privileges (transcends tenant boundaries)"
    )
    
    # Invitation tokens — stored as SHA-256(plaintext_uuid) (11.3)
    invitation_token = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="SHA-256 hex hash of the invitation UUID token"
    )
    invitation_token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Invitation token expiration time"
    )
    invitation_token_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When invitation token was used"
    )

    # Password reset tokens — stored as SHA-256(plaintext_uuid) (11.3)
    password_reset_token = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="SHA-256 hex hash of the password-reset UUID token"
    )
    password_reset_token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Password reset token expiration time"
    )
    password_reset_token_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When password reset token was used"
    )

    # Email verification (Phase 204): HMAC-signed token stored as SHA-256 hex of plaintext
    email_verified = models.BooleanField(
        default=False,
        help_text="Whether the user has confirmed ownership of their email address",
    )
    email_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When email was verified",
    )
    email_verification_token = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Hash of the email verification token (SHA-256 hex = 64 chars; 255 for spec/future formats)",
    )
    email_verification_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the current verification token was issued (expiry + resend throttling)",
    )

    # Token version for session invalidation
    token_version = models.IntegerField(
        default=1,
        help_text="Token version, incremented on password reset or role change"
    )

    # Account lockout (277.B.066) — progressive backoff
    failed_login_count = models.IntegerField(
        default=0,
        help_text="Consecutive failed login attempts since last successful login"
    )
    locked_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Account locked until this time (progressive backoff)"
    )
    lockout_level = models.IntegerField(
        default=0,
        help_text="Number of consecutive lockout periods triggered; drives progressive window doubling"
    )

    # CAN-SPAM / GDPR unsubscribe token (277.B.097)
    unsubscribe_token = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="SHA-256 hex hash of the 1-click unsubscribe token",
    )
    unsubscribe_token_created_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the current unsubscribe token was issued",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    
    class Meta:
        db_table = "users"
        ordering = ["email"]
        indexes = [
            models.Index(fields=["tenant", "email"]),
            models.Index(fields=["status"]),
            models.Index(fields=["invitation_token"]),
            models.Index(fields=["password_reset_token"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "email"],
                name="unique_tenant_email",
                condition=models.Q(tenant__isnull=False)
            )
        ]
    
    def __str__(self):
        if self.tenant_id is None:
            return f"{self.email} (Platform Admin)"
        try:
            return f"{self.email} ({self.tenant.name})"
        except Exception:
            return f"{self.email} (tenant_id={self.tenant_id})"
    
    def is_active(self) -> bool:
        """Check if user is active"""
        return self.status == UserStatus.ACTIVE
    
    def is_invited(self) -> bool:
        """Check if user is invited"""
        return self.status == UserStatus.INVITED
    
    def is_disabled(self) -> bool:
        """Check if user is disabled"""
        return self.status == UserStatus.DISABLED
    
    def increment_token_version(self):
        """Increment token version to invalidate existing sessions"""
        self.token_version += 1
        self.save(update_fields=["token_version", "updated_at"])
    
    def has_role(self, *role_names):
        """
        Check if user has any of the specified roles.

        Results are cached per (frozenset of role names) on the User instance
        in ``_role_cache`` to ensure repeated calls within a single request
        hit the DB only once.  The cache is invalidated by the
        ``_invalidate_user_role_cache`` signal handler whenever a UserRole row
        is saved or deleted for this user.

        Args:
            *role_names: One or more role names to check

        Returns:
            True if user has any of the specified roles, False otherwise
        """
        if self.is_platform_admin:
            return True

        cache_key = frozenset(role_names)
        cache = self.__dict__.setdefault("_role_cache", {})
        if cache_key in cache:
            return cache[cache_key]

        assigned_names = set(self.user_roles.values_list("role__name", flat=True))
        result = bool(assigned_names & set(role_names))

        cache[cache_key] = result
        # Register this live instance so signal handlers can clear its cache
        # when UserRole rows are added/removed (even via queryset.delete()).
        _live_user_instances[self.pk] = self
        return result


class Role(models.Model):
    """
    Role model representing a logical permission set within a tenant.
    
    Roles are tenant-scoped (except for platform-level roles).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="roles",
        help_text="Tenant this role belongs to"
    )
    name = models.CharField(
        max_length=100,
        help_text="Role name (e.g., TENANT_ADMIN, DATA_PROVIDER)"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Role description"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "roles"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["tenant", "name"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_tenant_role_name"
            )
        ]
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"


class UserRole(models.Model):
    """
    Many-to-many join table between User and Role.

    Represents role assignments for users.  The (user, tenant, role) unique
    constraint prevents duplicate role grants at the DB level; application
    code must use get_or_create to stay idempotent.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="user_roles"
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="user_role_assignments",
        help_text="Tenant this role assignment belongs to (denormalised from role.tenant)",
        null=True,  # nullable for the migration; set NOT NULL via 0009 data migration
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="user_roles"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_roles"
        ordering = ["user", "role"]
        indexes = [
            models.Index(fields=["user", "role"]),
            models.Index(fields=["user", "tenant"]),
        ]
        constraints = [
            # DB-level last-resort guarantee: one role grant per (user, tenant, role).
            models.UniqueConstraint(
                fields=["user", "tenant", "role"],
                name="unique_user_tenant_role"
            )
        ]

    def __str__(self):
        return f"{self.user.email} -> {self.role.name}"


class UserTenantMembership(models.Model):
    """
    Many-to-many user–tenant membership for tenant switching.

    A user may belong to multiple tenants (e.g. personal tenant + org tenants via invitation).
    UNIQUE(user_id, tenant_id). Per design D16 (Tenant Switch).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="tenant_memberships",
        help_text="User this membership belongs to",
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="user_memberships",
        help_text="Tenant this membership grants access to",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_tenant_memberships"
        ordering = ["user", "tenant"]
        indexes = [
            models.Index(fields=["user", "tenant"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "tenant"],
                name="unique_user_tenant_membership",
            )
        ]

    def __str__(self):
        return f"{self.user.email} -> {self.tenant.name}"


class PasswordHistory(models.Model):
    """
    Phase 225.1 — historical password hashes per user.

    Each row stores the Django hasher-produced ``password_hash`` (already
    salted + cost-parameterised) of a password the user once held. The
    application never reads plaintext back: re-use is checked via
    ``django.contrib.auth.hashers.check_password`` against each stored hash.

    The ``unique_together (user, password_hash)`` constraint is a defensive
    guarantee against duplicate rows — because Django salts each hash, the
    same plaintext produces a different stored hash on each call, so
    collisions at the string level are vanishingly unlikely in practice.

    Rows are ordered newest-first so service code can take a simple
    ``[:window]`` slice when evaluating reuse.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="password_history",
        help_text="User whose password was hashed here",
    )
    password_hash = models.CharField(
        max_length=255,
        help_text="Django hasher output (algorithm$iterations$salt$hash) for a prior password",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "password_history"
        ordering = ["-created_at"]
        indexes = [
            # Named explicitly so `makemigrations --check` does not drift from
            # the migration that introduces this index (0016_passwordhistory).
            models.Index(
                fields=["user", "-created_at"],
                name="password_history_user_ts_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "password_hash"],
                name="unique_user_password_hash",
            ),
        ]

    def __str__(self):  # pragma: no cover — trivial repr
        return f"PasswordHistory(user_id={self.user_id}, created_at={self.created_at.isoformat()})"


# ---------------------------------------------------------------------------
# Signal handlers: invalidate the per-instance _role_cache on the affected
# User object whenever a UserRole row is created, updated, or deleted.
# This ensures has_role() is not stale within long-lived process memory.
# ---------------------------------------------------------------------------

def _clear_user_role_cache(user_id) -> None:
    """
    Clear _role_cache on the live User instance for *user_id* (if any).

    ``queryset.delete()`` creates fresh UserRole Python objects during its
    Collector phase, so ``instance.user`` in the signal handler is never the
    same Python object as the one held by the caller.  The
    ``_live_user_instances`` WeakValueDictionary maps PK → live instance,
    allowing the cache to be cleared on the exact object without an extra
    DB query or keeping the User alive unnecessarily.
    """
    user = _live_user_instances.get(user_id)
    if user is not None:
        user.__dict__.pop("_role_cache", None)


@receiver(post_save, sender=UserRole)
def _invalidate_user_role_cache_on_save(sender, instance, **kwargs):
    """Clear role cache on the user when a UserRole row is saved."""
    _clear_user_role_cache(instance.user_id)


@receiver(post_delete, sender=UserRole)
def _invalidate_user_role_cache_on_delete(sender, instance, **kwargs):
    """Clear role cache on the user when a UserRole row is deleted."""
    _clear_user_role_cache(instance.user_id)
