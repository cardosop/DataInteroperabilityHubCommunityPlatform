"""
User Management Models

Defines User and Role models with relationships.
"""
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.core.validators import EmailValidator


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
        null=True,
        blank=True,
        help_text="User display name"
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
    
    # Invitation tokens
    invitation_token = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID token for invitation acceptance"
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
    
    # Password reset tokens
    password_reset_token = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID token for password reset"
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
    
    # Token version for session invalidation
    token_version = models.IntegerField(
        default=1,
        help_text="Token version, incremented on password reset or role change"
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
        return f"{self.email} ({self.tenant.name if self.tenant else 'Platform Admin'})"
    
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
        
        Args:
            *role_names: One or more role names to check
            
        Returns:
            True if user has any of the specified roles, False otherwise
        """
        if self.is_platform_admin:
            return True
        
        if hasattr(self, 'user_roles'):
            user_role_names = [ur.role.name for ur in self.user_roles.all()]
            return any(role_name in user_role_names for role_name in role_names)
        
        return False


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
    
    Represents role assignments for users.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="user_roles"
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
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role"],
                name="unique_user_role"
            )
        ]
    
    def __str__(self):
        return f"{self.user.email} -> {self.role.name}"

