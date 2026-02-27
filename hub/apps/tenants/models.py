"""
Tenant Management Models

Defines Tenant model with status and KYC status enums, and TenantConfig model for per-tenant configuration.
"""

import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone


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
    PENDING_REVIEW = "PENDING_REVIEW", "Pending review"
    VERIFIED = "VERIFIED", "Verified"


class PlanTier(models.TextChoices):
    """Plan tier enumeration"""

    FREE = "FREE", "Free"
    PRO = "PRO", "Pro"
    ENTERPRISE = "ENTERPRISE", "Enterprise"


class TenantPlan(models.Model):
    """
    Tenant Plan model representing subscription plans with limits.

    Plans define resource limits (max_assets, max_api_calls_per_month, etc.)
    that are enforced per tenant.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255, unique=True, help_text="Plan name (e.g., 'Free Plan', 'Pro Plan')"
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text="URL-safe plan identifier (e.g., 'free', 'pro', 'enterprise')",
    )
    tier = models.CharField(
        max_length=20, choices=PlanTier.choices, help_text="Plan tier: FREE, PRO, or ENTERPRISE"
    )
    limits_json = models.JSONField(
        default=default_empty_dict,
        help_text="Plan limits as JSON (e.g., {'max_assets': 10, 'max_api_calls_per_month': 10000, 'max_scheduled_runs_per_month': 100})",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this plan is currently active and available for subscription",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenant_plans"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["tier"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.slug})"

    def get_limit(self, limit_key: str, default=None):
        """
        Get a specific limit value from limits_json.

        Args:
            limit_key: Key in limits_json (e.g., 'max_assets')
            default: Default value if limit_key not found

        Returns:
            Limit value or default
        """
        return self.limits_json.get(limit_key, default)


class Tenant(models.Model):
    """
    Tenant model representing an organization or individual user.

    Each tenant is isolated from others with row-level security.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255, unique=True, help_text="Tenant name (unique per environment)"
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        validators=[
            RegexValidator(
                regex=r"^[a-z0-9-]+$",
                message="Slug must contain only lowercase letters, numbers, and hyphens.",
            )
        ],
        help_text="URL-safe tenant identifier",
    )
    status = models.CharField(
        max_length=20,
        choices=TenantStatus.choices,
        default=TenantStatus.ACTIVE,
        help_text="Tenant status: ACTIVE, SUSPENDED, or DELETED",
    )
    kyc_status = models.CharField(
        max_length=20,
        choices=KYCStatus.choices,
        default=KYCStatus.UNVERIFIED,
        help_text="KYC verification status: UNVERIFIED, PENDING_REVIEW (submission with provider), or VERIFIED",
    )
    region = models.CharField(
        max_length=100, null=True, blank=True, help_text="Cloud region (e.g., us-east-1, eu-west-1)"
    )
    plan = models.ForeignKey(
        "tenants.TenantPlan",
        on_delete=models.SET_NULL,
        related_name="tenants",
        null=True,
        blank=True,
        help_text="Subscription plan for this tenant",
    )
    deleted_at = models.DateTimeField(
        null=True, blank=True, help_text="Timestamp when tenant was marked for deletion"
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
            models.Index(fields=["plan"]),
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
        help_text="Tenant this configuration belongs to",
    )

    # DQ Profile Configuration
    default_dq_profile = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Default DQ profile key (e.g., intake_basic_gx, intake_basic_soda)",
    )

    # Compliance Configuration
    allowed_compliance_regimes = models.JSONField(
        default=default_empty_list,
        blank=True,
        help_text="List of compliance regimes available to this tenant (e.g., ['GDPR', 'LGPD', 'CCPA'])",
    )
    default_compliance_regimes = models.JSONField(
        default=default_empty_list,
        blank=True,
        help_text="Default compliance regimes applied to intake flows (subset of allowed_compliance_regimes)",
    )

    # Data Retention
    data_retention_days = models.IntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(90, message="Data retention must be at least 90 days"),
            MaxValueValidator(3650, message="Data retention cannot exceed 3650 days (10 years)"),
        ],
        help_text="Data retention period in days (90-3650)",
    )

    # Rate Limits (JSON structure)
    # API Gateway uses key "api_gateway_requests_per_hour" (int, requests per hour).
    rate_limits = models.JSONField(
        default=default_empty_dict,
        null=True,
        blank=True,
        help_text="Per-endpoint category rate limits (JSON). API Gateway: api_gateway_requests_per_hour (int).",
    )

    # File Size Limits
    max_file_size_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum file size for uploads in bytes",
    )

    # Job Concurrency Limits
    max_job_concurrency = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum concurrent running jobs for this tenant",
    )
    max_queued_jobs = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum queued jobs for this tenant",
    )

    # SSO Configuration (JSON structure)
    sso_config = models.JSONField(
        default=default_empty_dict,
        null=True,
        blank=True,
        help_text="SSO configuration (SAML and OIDC settings)",
    )

    # ODPS $ref Resolver Configuration (JSON structure)
    # Overrides global ODPS refs configuration for this tenant
    # Structure:
    # {
    #   "url_allowlist": ["https://*.example.com", "https://schemas.trusted.com"],
    #   "url_denylist": ["http://*", "https://*.malicious.com"]
    # }
    odps_refs_config = models.JSONField(
        default=default_empty_dict,
        null=True,
        blank=True,
        help_text="ODPS $ref resolver configuration (URL allowlist/denylist overrides)",
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
                raise ValidationError(
                    {
                        "default_compliance_regimes": "Default compliance regimes must be a subset of allowed compliance regimes."
                    }
                )

    def save(self, *args, **kwargs):
        """Override save to run clean validation"""
        self.full_clean()
        super().save(*args, **kwargs)


class TenantUsageSummary(models.Model):
    """
    Tenant Usage Summary model for aggregating per-tenant usage metrics.

    Stores aggregated usage data for billing and admin purposes.
    Can be recalculated periodically or on-demand.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="usage_summaries",
        help_text="Tenant this usage summary belongs to",
    )
    period_start = models.DateTimeField(
        help_text="Start of the usage period (typically start of month)"
    )
    period_end = models.DateTimeField(help_text="End of the usage period (typically end of month)")

    # Usage metrics
    api_calls_count = models.BigIntegerField(default=0, help_text="Total API calls in period")
    asset_count = models.IntegerField(default=0, help_text="Total assets (current count)")
    dataset_count = models.IntegerField(default=0, help_text="Total datasets (current count)")
    scheduled_ingestion_runs_count = models.IntegerField(
        default=0, help_text="Total scheduled ingestion runs in period"
    )
    scheduled_export_runs_count = models.IntegerField(
        default=0, help_text="Total scheduled export runs in period"
    )
    storage_bytes = models.BigIntegerField(default=0, help_text="Total storage used in bytes")

    # Cost metrics (optional, for billing)
    ingestion_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total cost for scheduled ingestion runs in period",
    )

    # Metadata
    calculated_at = models.DateTimeField(
        auto_now=True, help_text="When this summary was last calculated"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenant_usage_summaries"
        ordering = ["-period_start"]
        indexes = [
            models.Index(fields=["tenant", "period_start"]),
            models.Index(fields=["tenant", "period_end"]),
            models.Index(fields=["period_start", "period_end"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "period_start", "period_end"],
                name="unique_tenant_period_usage_summary",
            )
        ]

    def __str__(self):
        return f"Usage summary for {self.tenant.name} ({self.period_start} to {self.period_end})"

    def get_storage_gb(self) -> float:
        """Get storage in GB"""
        return self.storage_bytes / (1024**3)
