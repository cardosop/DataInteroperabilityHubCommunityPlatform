"""
Tenant Management Models

Defines Tenant model with status and KYC status enums.
"""
import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator


class TenantStatus(models.TextChoices):
    """Tenant status enumeration"""
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"
    DELETED = "DELETED", "Deleted"


class KYCStatus(models.TextChoices):
    """KYC status enumeration"""
    UNVERIFIED = "UNVERIFIED", "Unverified"
    VERIFIED = "VERIFIED", "Verified"


class Tenant(models.Model):
    """
    Tenant model representing an organization or individual user.
    
    Each tenant is isolated from others with row-level security.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True, help_text="Tenant name (unique per environment)")
    slug = models.SlugField(
        max_length=255,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[a-z0-9-]+$',
                message='Slug must contain only lowercase letters, numbers, and hyphens.'
            )
        ],
        help_text="URL-safe tenant identifier"
    )
    status = models.CharField(
        max_length=20,
        choices=TenantStatus.choices,
        default=TenantStatus.ACTIVE,
        help_text="Tenant status: ACTIVE, SUSPENDED, or DELETED"
    )
    kyc_status = models.CharField(
        max_length=20,
        choices=KYCStatus.choices,
        default=KYCStatus.UNVERIFIED,
        help_text="KYC verification status: UNVERIFIED or VERIFIED"
    )
    region = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Cloud region (e.g., us-east-1, eu-west-1)"
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when tenant was marked for deletion"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "tenants"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status"]),
            models.Index(fields=["kyc_status"]),
            models.Index(fields=["region"]),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.slug})"
    
    def is_active(self) -> bool:
        """Check if tenant is active"""
        return self.status == TenantStatus.ACTIVE
    
    def is_suspended(self) -> bool:
        """Check if tenant is suspended"""
        return self.status == TenantStatus.SUSPENDED
    
    def is_deleted(self) -> bool:
        """Check if tenant is deleted"""
        return self.status == TenantStatus.DELETED
    
    def can_publish_to_marketplace(self) -> bool:
        """Check if tenant can publish to marketplace (requires KYC verification)"""
        return self.kyc_status == KYCStatus.VERIFIED and self.is_active()
    
    def suspend(self):
        """Suspend the tenant (read-only mode)"""
        if self.status == TenantStatus.DELETED:
            raise ValueError("Cannot suspend a deleted tenant")
        self.status = TenantStatus.SUSPENDED
        self.save(update_fields=["status", "updated_at"])
    
    def reactivate(self):
        """Reactivate a suspended tenant"""
        if self.status != TenantStatus.SUSPENDED:
            raise ValueError("Can only reactivate suspended tenants")
        self.status = TenantStatus.ACTIVE
        self.save(update_fields=["status", "updated_at"])
    
    def soft_delete(self):
        """Mark tenant for deletion (soft delete)"""
        self.status = TenantStatus.DELETED
        self.deleted_at = timezone.now()
        self.save(update_fields=["status", "deleted_at", "updated_at"])

