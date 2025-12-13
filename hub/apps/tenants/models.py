"""
Tenant Management Models

Defines Tenant model with status and KYC status enums, and TenantConfig model for per-tenant configuration.
"""
import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError


def default_empty_list():
    """Return a new empty list. Used as default for JSONField to avoid mutable default argument."""
    return []


def default_empty_dict():
    """Return a new empty dict. Used as default for JSONField to avoid mutable default argument."""
    return {}


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


class TenantConfig(models.Model):
    """
    Tenant Configuration model storing per-tenant configuration settings.
    
    Includes DQ profiles, compliance regimes, data retention, rate limits,
    file size limits, and job concurrency limits.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="config",
        help_text="Tenant this configuration belongs to"
    )
    
    # DQ Profile Configuration
    default_dq_profile = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Default DQ profile key (e.g., intake_basic_gx, intake_basic_soda)"
    )
    
    # Compliance Configuration
    allowed_compliance_regimes = models.JSONField(
        default=default_empty_list,
        blank=True,
        help_text="List of compliance regimes available to this tenant (e.g., ['GDPR', 'LGPD', 'CCPA'])"
    )
    default_compliance_regimes = models.JSONField(
        default=default_empty_list,
        blank=True,
        help_text="Default compliance regimes applied to intake flows (subset of allowed_compliance_regimes)"
    )
    
    # Data Retention
    data_retention_days = models.IntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(90, message="Data retention must be at least 90 days"),
            MaxValueValidator(3650, message="Data retention cannot exceed 3650 days (10 years)")
        ],
        help_text="Data retention period in days (90-3650)"
    )
    
    # Rate Limits (JSON structure)
    rate_limits = models.JSONField(
        default=default_empty_dict,
        null=True,
        blank=True,
        help_text="Per-endpoint category rate limits (JSON structure)"
    )
    
    # File Size Limits
    max_file_size_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum file size for uploads in bytes"
    )
    
    # Job Concurrency Limits
    max_job_concurrency = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum concurrent running jobs for this tenant"
    )
    max_queued_jobs = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum queued jobs for this tenant"
    )
    
    # SSO Configuration (JSON structure)
    sso_config = models.JSONField(
        default=default_empty_dict,
        null=True,
        blank=True,
        help_text="SSO configuration (SAML and OIDC settings)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "tenant_configs"
        ordering = ["tenant"]
        indexes = [
            models.Index(fields=["tenant"]),
        ]
    
    def __str__(self):
        return f"Config for {self.tenant.name}"
    
    def clean(self):
        """Validate model-level constraints"""
        super().clean()
        
        # Validate default_compliance_regimes is subset of allowed_compliance_regimes
        if self.default_compliance_regimes and self.allowed_compliance_regimes:
            default_set = set(self.default_compliance_regimes)
            allowed_set = set(self.allowed_compliance_regimes)
            if not default_set.issubset(allowed_set):
                raise ValidationError({
                    'default_compliance_regimes': 'Default compliance regimes must be a subset of allowed compliance regimes.'
                })
    
    def save(self, *args, **kwargs):
        """Override save to run clean validation"""
        self.full_clean()
        super().save(*args, **kwargs)
