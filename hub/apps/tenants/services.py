"""
Tenant Service

Business logic for tenant operations.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from hub.apps.core.events.service_publishers import TenantEventPublisher
from hub.apps.core.services.base import BaseService, NotFoundError, PermissionError, ValidationError
from hub.apps.tenants.models import (
    KYCStatus,
    PlanCategory,
    PlanTier,
    Tenant,
    TenantConfig,
    TenantPlan,
    TenantStatus,
    TenantUsageSummary,
)
from hub.apps.tenants.validators import get_platform_defaults


def get_tenant_config(tenant: Tenant) -> Dict[str, Any]:
    """
    Get tenant configuration with platform defaults.

    Returns a dictionary with all configuration values, using platform defaults
    for any values not set in the tenant's configuration.

    Args:
        tenant: Tenant instance

    Returns:
        Dictionary with complete configuration (tenant values + platform defaults)
    """
    platform_defaults = get_platform_defaults()

    try:
        # Get config directly from database to avoid caching issues
        config = TenantConfig.objects.get(tenant=tenant)
    except TenantConfig.DoesNotExist:
        # No tenant config exists, return platform defaults
        return {
            **platform_defaults,
            "tenant_id": str(tenant.id),
            "created_at": None,
            "updated_at": None,
        }

    # Merge tenant config with platform defaults
    tenant_rate_limits = config.rate_limits if config.rate_limits else {}
    merged_rate_limits = platform_defaults["rate_limits"].copy()
    merged_rate_limits.update(tenant_rate_limits)

    # Return actual saved values from config. For fields that can be None, use platform defaults if None.
    # For JSONField lists (which have default=default_empty_list), they're never None, so return the actual value.
    # The key insight: if a config exists and has been updated, return its actual values.
    # Only use platform defaults when the field is explicitly None (for nullable fields) or when config doesn't exist.
    result = {
        "tenant_id": str(tenant.id),
        "default_dq_profile": (
            config.default_dq_profile
            if config.default_dq_profile
            else platform_defaults["default_dq_profile"]
        ),
        # For JSONField lists: empty list means "use platform default" (explicit empty = no regimes configured)
        # Use explicit len() check since JSONField default_empty_list means we never get None, only []
        "allowed_compliance_regimes": (
            config.allowed_compliance_regimes
            if (config.allowed_compliance_regimes and len(config.allowed_compliance_regimes) > 0)
            else platform_defaults["allowed_compliance_regimes"]
        ),
        "default_compliance_regimes": (
            config.default_compliance_regimes
            if (config.default_compliance_regimes and len(config.default_compliance_regimes) > 0)
            else platform_defaults["default_compliance_regimes"]
        ),
        "data_retention_days": (
            config.data_retention_days
            if config.data_retention_days is not None
            else platform_defaults["data_retention_days"]
        ),
        "rate_limits": merged_rate_limits,
        "max_file_size_bytes": (
            config.max_file_size_bytes
            if config.max_file_size_bytes is not None
            else platform_defaults["max_file_size_bytes"]
        ),
        "max_job_concurrency": (
            config.max_job_concurrency
            if config.max_job_concurrency is not None
            else platform_defaults["max_job_concurrency"]
        ),
        "max_queued_jobs": (
            config.max_queued_jobs
            if config.max_queued_jobs is not None
            else platform_defaults["max_queued_jobs"]
        ),
        "trust_signals_enabled": (
            config.trust_signals_enabled
            if config.trust_signals_enabled is not None
            else platform_defaults["trust_signals_enabled"]
        ),
        "versioning_enabled": (
            config.versioning_enabled
            if config.versioning_enabled is not None
            else platform_defaults["versioning_enabled"]
        ),
        "workflows_enabled": (
            config.workflows_enabled
            if config.workflows_enabled is not None
            else platform_defaults["workflows_enabled"]
        ),
        "compliance_risk_threshold": config.compliance_risk_threshold,
        "created_at": config.created_at.isoformat() if config.created_at else None,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }

    return result


def get_tenant_config_value(tenant: Tenant, key: str, default: Any = None) -> Any:
    """
    Get a specific tenant configuration value with platform default fallback.

    Args:
        tenant: Tenant instance
        key: Configuration key
        default: Optional custom default value (if provided, overrides platform default)

    Returns:
        Configuration value: tenant-specific value if set, otherwise custom default if provided,
        otherwise platform default
    """
    # Check if tenant has explicit config value
    try:
        config = tenant.config
        # Map of config keys to their corresponding model attributes
        key_to_attr = {
            "default_dq_profile": ("default_dq_profile", lambda v: v),
            "allowed_compliance_regimes": ("allowed_compliance_regimes", lambda v: v),
            "default_compliance_regimes": ("default_compliance_regimes", lambda v: v),
            "data_retention_days": ("data_retention_days", lambda v: v if v is not None else None),
            "max_file_size_bytes": ("max_file_size_bytes", lambda v: v if v is not None else None),
            "max_job_concurrency": ("max_job_concurrency", lambda v: v if v is not None else None),
            "max_queued_jobs": ("max_queued_jobs", lambda v: v if v is not None else None),
            "trust_signals_enabled": ("trust_signals_enabled", lambda v: v if v is not None else None),
            "versioning_enabled": ("versioning_enabled", lambda v: v if v is not None else None),
            "workflows_enabled": ("workflows_enabled", lambda v: v if v is not None else None),
            "compliance_risk_threshold": ("compliance_risk_threshold", lambda v: v),
        }

        if key in key_to_attr:
            attr_name, validator = key_to_attr[key]
            tenant_value = validator(getattr(config, attr_name, None))
            if tenant_value is not None:
                return tenant_value
    except ObjectDoesNotExist:
        pass  # No tenant config exists

    # If custom default provided, use it (overrides platform default)
    if default is not None:
        return default

    # Fall back to platform default
    config_dict = get_tenant_config(tenant)
    return config_dict.get(key)


def get_tenant_dq_profile(tenant_id: str) -> str:
    """
    Get tenant DQ profile with platform default fallback.

    Args:
        tenant_id: Tenant UUID as string

    Returns:
        DQ profile name
    """
    import uuid

    try:
        tenant = Tenant.objects.get(id=uuid.UUID(tenant_id))
        config_dict = get_tenant_config(tenant)
        return config_dict.get("default_dq_profile", "intake_basic_gx")
    except (Tenant.DoesNotExist, ValueError):
        platform_defaults = get_platform_defaults()
        return platform_defaults.get("default_dq_profile", "intake_basic_gx")


def get_tenant_compliance_regimes(tenant_id: str) -> list:
    """
    Get tenant default compliance regimes with platform default fallback.

    Args:
        tenant_id: Tenant UUID as string

    Returns:
        List of compliance regime codes
    """
    import uuid

    try:
        tenant = Tenant.objects.get(id=uuid.UUID(tenant_id))
        config_dict = get_tenant_config(tenant)
        return config_dict.get("default_compliance_regimes", ["GDPR", "LGPD"])
    except (Tenant.DoesNotExist, ValueError):
        platform_defaults = get_platform_defaults()
        return platform_defaults.get("default_compliance_regimes", ["GDPR", "LGPD"])


def get_tenant_file_size_limit(tenant_id: str) -> int:
    """
    Get tenant file size limit with platform default fallback.

    Args:
        tenant_id: Tenant UUID as string

    Returns:
        Maximum file size in bytes
    """
    import uuid

    try:
        tenant = Tenant.objects.get(id=uuid.UUID(tenant_id))
        config_dict = get_tenant_config(tenant)
        return config_dict.get("max_file_size_bytes", 10737418240)
    except (Tenant.DoesNotExist, ValueError):
        platform_defaults = get_platform_defaults()
        return platform_defaults.get("max_file_size_bytes", 10737418240)


def get_tenant_job_limits(tenant_id: str) -> Dict[str, int]:
    """
    Get tenant job concurrency and queuing limits with platform default fallback.

    Args:
        tenant_id: Tenant UUID as string

    Returns:
        Dictionary with max_job_concurrency and max_queued_jobs
    """
    import uuid

    try:
        tenant = Tenant.objects.get(id=uuid.UUID(tenant_id))
        config_dict = get_tenant_config(tenant)
        return {
            "max_job_concurrency": config_dict.get("max_job_concurrency", 5),
            "max_queued_jobs": config_dict.get("max_queued_jobs", 50),
        }
    except (Tenant.DoesNotExist, ValueError):
        platform_defaults = get_platform_defaults()
        return {
            "max_job_concurrency": platform_defaults.get("max_job_concurrency", 5),
            "max_queued_jobs": platform_defaults.get("max_queued_jobs", 50),
        }


class TenantService(BaseService, TenantEventPublisher):
    """
    Service for tenant operations.

    Provides business logic for retrieving, creating, updating, and deleting tenants.
    """

    service_name = "tenant_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize TenantService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID
        """
        # Set attributes directly (BaseService doesn't have __init__)
        self.tenant_id = tenant_id
        self.user_id = user_id
        # Initialize event publisher
        TenantEventPublisher.__init__(self, tenant_id=tenant_id, user_id=user_id)

    def get_tenant(self, tenant_id: str) -> Tenant:
        """
        Get tenant by ID.

        Args:
            tenant_id: Tenant ID

        Returns:
            Tenant instance

        Raises:
            NotFoundError: If tenant not found
        """
        return self.execute_with_metrics(
            operation="get_tenant",
            tenant_id=tenant_id,
            func=lambda: self.get_resource_or_raise(Tenant, tenant_id),
        )

    def validate_kyc_verified(self, tenant_id: str) -> Tenant:
        """
        Validate that tenant exists and has verified KYC status.

        Args:
            tenant_id: Tenant ID

        Returns:
            Tenant instance

        Raises:
            NotFoundError: If tenant not found
            PermissionError: If tenant KYC is not verified
        """

        def _validate():
            tenant = self.get_resource_or_raise(Tenant, tenant_id)

            if tenant.kyc_status != KYCStatus.VERIFIED:
                raise PermissionError(
                    f"Tenant must have VERIFIED KYC status (current: {tenant.kyc_status})"
                )

            return tenant

        return self.execute_with_metrics(
            operation="validate_kyc_verified", tenant_id=tenant_id, func=_validate
        )

    @transaction.atomic
    def create_tenant(self, name: str, slug: str, region: Optional[str] = None, **kwargs) -> Tenant:
        """
        Create a new tenant.

        Args:
            name: Tenant name
            slug: Tenant slug (URL-safe identifier)
            region: Optional cloud region
            **kwargs: Additional keyword arguments passed to event publisher

        Returns:
            Created Tenant instance

        Raises:
            ValidationError: If tenant creation fails
        """

        def _create():
            if Tenant.objects.filter(slug=slug).exists():
                raise ValidationError(
                    f"A tenant with slug '{slug}' already exists.",
                    code="DUPLICATE_SLUG",
                )
            tenant = Tenant.objects.create(
                name=name,
                slug=slug,
                region=region,
                status=TenantStatus.ACTIVE,
                kyc_status=KYCStatus.UNVERIFIED,
            )

            # Publish tenant.created event
            self.publish_tenant_created(
                tenant_id=str(tenant.id),
                name=tenant.name,
                slug=tenant.slug,
                status=tenant.status,
                kyc_status=tenant.kyc_status,
                region=tenant.region,
                **kwargs,
            )

            return tenant

        return self.execute_with_metrics(
            operation="create_tenant", tenant_id=None, func=_create  # No tenant_id yet for creation
        )

    @transaction.atomic
    def update_tenant(
        self,
        tenant_id: str,
        name: Optional[str] = None,
        slug: Optional[str] = None,
        kyc_status: Optional[str] = None,
        region: Optional[str] = None,
        **kwargs,
    ) -> Tenant:
        """
        Update tenant.

        Args:
            tenant_id: Tenant ID
            name: Optional new name
            slug: Optional new slug
            kyc_status: Optional new KYC status
            region: Optional new region
            **kwargs: Additional keyword arguments passed to event publisher

        Returns:
            Updated Tenant instance

        Raises:
            NotFoundError: If tenant not found
            ValidationError: If update fails
        """

        def _update():
            tenant = self.get_resource_or_raise(Tenant, tenant_id)
            previous_status = tenant.status

            # Track changes
            changes = {}
            if name is not None and tenant.name != name:
                changes["name"] = {"old": tenant.name, "new": name}
                tenant.name = name
            if slug is not None and tenant.slug != slug:
                changes["slug"] = {"old": tenant.slug, "new": slug}
                tenant.slug = slug
            if kyc_status is not None and tenant.kyc_status != kyc_status:
                changes["kyc_status"] = {"old": tenant.kyc_status, "new": kyc_status}
                tenant.kyc_status = kyc_status
            if region is not None and tenant.region != region:
                changes["region"] = {"old": tenant.region, "new": region}
                tenant.region = region

            # Only save and publish if there are changes
            if changes:
                tenant.save()
                new_status = tenant.status

                # Publish tenant.updated event
                self.publish_tenant_updated(
                    tenant_id=str(tenant.id),
                    changes=changes,
                    previous_status=previous_status,
                    new_status=new_status,
                    **kwargs,
                )

            return tenant

        return self.execute_with_metrics(
            operation="update_tenant", tenant_id=tenant_id, func=_update
        )

    @transaction.atomic
    def delete_tenant(self, tenant_id: str, reason: Optional[str] = None, **kwargs) -> Tenant:
        """
        Delete a tenant (soft delete).

        Args:
            tenant_id: Tenant ID
            reason: Optional reason for deletion
            **kwargs: Additional keyword arguments passed to event publisher

        Returns:
            Deleted Tenant instance

        Raises:
            NotFoundError: If tenant not found
            ValidationError: If tenant is already deleted
        """

        def _delete():
            # Use all_objects to find even soft-deleted tenants (needed for
            # the "already deleted" check to return the correct error).
            try:
                tenant = Tenant.all_objects.get(pk=tenant_id)
            except Tenant.DoesNotExist:
                raise NotFoundError(f"Tenant with id {tenant_id} not found")

            if tenant.status == TenantStatus.DELETED or tenant.deleted_at is not None:
                raise ValidationError("Tenant is already deleted")

            # Soft delete tenant
            tenant.soft_delete()

            # Publish tenant.deleted event
            self.publish_tenant_deleted(tenant_id=str(tenant.id), reason=reason, **kwargs)

            return tenant

        return self.execute_with_metrics(
            operation="delete_tenant", tenant_id=tenant_id, func=_delete
        )

    @transaction.atomic
    def update_tenant_config(
        self,
        tenant_id: str,
        default_dq_profile: Optional[str] = None,
        allowed_compliance_regimes: Optional[list] = None,
        default_compliance_regimes: Optional[list] = None,
        data_retention_days: Optional[int] = None,
        rate_limits: Optional[Dict[str, Any]] = None,
        max_file_size_bytes: Optional[int] = None,
        max_job_concurrency: Optional[int] = None,
        max_queued_jobs: Optional[int] = None,
        trust_signals_enabled: Optional[bool] = None,
        versioning_enabled: Optional[bool] = None,
        workflows_enabled: Optional[bool] = None,
        compliance_risk_threshold: Optional[str] = None,
        **kwargs,
    ) -> TenantConfig:
        """
        Update tenant configuration.

        Publishes tenant.quota.changed events for any quota-related fields that change.

        Args:
            tenant_id: Tenant ID
            default_dq_profile: Optional DQ profile
            allowed_compliance_regimes: Optional list of allowed compliance regimes
            default_compliance_regimes: Optional list of default compliance regimes
            data_retention_days: Optional data retention days
            rate_limits: Optional rate limits dictionary
            max_file_size_bytes: Optional max file size in bytes
            max_job_concurrency: Optional max job concurrency
            max_queued_jobs: Optional max queued jobs
            **kwargs: Additional keyword arguments passed to event publisher

        Returns:
            Updated TenantConfig instance

        Raises:
            NotFoundError: If tenant not found
            ValidationError: If update fails
        """

        def _update_config():
            tenant = self.get_resource_or_raise(Tenant, tenant_id)

            # Get or create tenant config - use select_for_update to prevent race conditions
            config, created = TenantConfig.objects.select_for_update().get_or_create(tenant=tenant)

            # Track quota changes
            quota_fields = {
                "default_dq_profile": ("dq_profile", default_dq_profile),
                "allowed_compliance_regimes": ("compliance", allowed_compliance_regimes),
                "default_compliance_regimes": ("compliance", default_compliance_regimes),
                "data_retention_days": ("data_retention", data_retention_days),
                "max_file_size_bytes": ("file_size", max_file_size_bytes),
                "max_job_concurrency": ("job_concurrency", max_job_concurrency),
                "max_queued_jobs": ("job_concurrency", max_queued_jobs),
                "trust_signals_enabled": ("trust_signals", trust_signals_enabled),
                "versioning_enabled": ("versioning", versioning_enabled),
                "workflows_enabled": ("workflows", workflows_enabled),
            }

            # Track which fields are being updated
            updated_fields = []

            # Update fields and track changes
            for field_name, (quota_type, new_value) in quota_fields.items():
                if new_value is not None:
                    old_value = getattr(config, field_name, None)
                    # For list fields, compare as sets to handle order differences
                    if isinstance(old_value, list) and isinstance(new_value, list):
                        values_differ = set(old_value) != set(new_value)
                    else:
                        values_differ = old_value != new_value

                    if values_differ:
                        # For JSONField, we need to assign the value directly
                        # Django's JSONField handles serialization automatically
                        setattr(config, field_name, new_value)
                        updated_fields.append(field_name)

                        # Publish quota changed event
                        self.publish_tenant_quota_changed(
                            tenant_id=str(tenant.id),
                            quota_type=quota_type,
                            quota_field=field_name,
                            previous_value=old_value,
                            new_value=new_value,
                            **kwargs,
                        )

                        # Force Django to mark the field as changed for JSONField
                        # This ensures the field is included in the save
                        if hasattr(config, "_state"):
                            config._state.adding = False

            # Track rate_limits update
            if rate_limits is not None:
                old_rate_limits = config.rate_limits or {}
                if old_rate_limits != rate_limits:
                    config.rate_limits = rate_limits
                    updated_fields.append("rate_limits")

                    # Publish quota changed event for rate limits
                    self.publish_tenant_quota_changed(
                        tenant_id=str(tenant.id),
                        quota_type="rate_limits",
                        quota_field="rate_limits",
                        previous_value=old_rate_limits,
                        new_value=rate_limits,
                        **kwargs,
                    )

            if compliance_risk_threshold is not None:
                prev_thr = getattr(
                    config, "compliance_risk_threshold", None
                )
                if prev_thr != compliance_risk_threshold:
                    config.compliance_risk_threshold = compliance_risk_threshold
                    updated_fields.append("compliance_risk_threshold")

            # Save config - always save all fields to ensure JSONField changes are persisted
            # Using update_fields can sometimes cause issues with JSONField, so we save all fields
            config.save()

            # Refresh from database to ensure we have the latest values
            config.refresh_from_db()

            return config

        return self.execute_with_metrics(
            operation="update_tenant_config", tenant_id=tenant_id, func=_update_config
        )


class PlanLimitService(BaseService):
    """
    Service for checking and enforcing plan limits.

    Provides business logic for:
    - Checking if a tenant has exceeded plan limits
    - Enforcing limits with proper error responses

    The check_limit() method acquires a row-level lock on the Tenant row
    and queries the current count internally, eliminating TOCTOU race
    conditions where two concurrent requests could both pass the limit check.
    """

    service_name = "plan_limit_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize PlanLimitService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

    def check_limit(
        self, tenant_id: str, limit_key: str, delta: int = 1
    ) -> Dict[str, Any]:
        """
        Check if tenant has exceeded plan limit for a specific limit key.

        Acquires a SELECT FOR UPDATE lock on the Tenant row to serialize
        concurrent limit checks. The current usage count is queried internally
        from the resource counter registry — callers must NOT pass their own count.

        Must be called inside a transaction.atomic() block.

        Args:
            tenant_id: Tenant ID
            limit_key: Limit key (e.g., 'max_assets', 'max_api_calls_per_month')
            delta: Number of resources being created (default: 1)

        Returns:
            Dictionary with 'allowed' (bool), 'current' (int), 'max' (int or None),
            'remaining' (int or None), 'limit_key' (str)

        Raises:
            ValidationError: If limit exceeded (with code 'plan_limit_exceeded')
            NotFoundError: If tenant or plan not found
        """
        from hub.apps.billing.limit_registry import get_resource_count

        def _check():
            # Acquire row-level lock on the tenant to serialize concurrent checks.
            # This prevents two requests from both reading count=9 (limit=10)
            # and both proceeding to create, resulting in 11 resources.
            #
            # Note: select_for_update() cannot be combined with
            # select_related("plan") because plan is a nullable FK
            # (LEFT OUTER JOIN) and PostgreSQL forbids FOR UPDATE on
            # the nullable side of an outer join.
            tenant = (
                Tenant.objects.select_for_update()
                .filter(pk=tenant_id)
                .first()
            )
            if not tenant:
                raise NotFoundError(
                    f"Tenant {tenant_id} not found",
                    code="TENANT_NOT_FOUND",
                )

            # Route ML limit keys to tenant.ml_plan; everything
            # else goes to the base plan.
            is_ml_key = limit_key in TenantPlan.ML_LIMIT_KEYS

            if is_ml_key:
                plan = tenant.ml_plan
                if not plan:
                    # No ML plan → max_limit = 0 (no ML access)
                    plan = None
            else:
                plan = tenant.plan
                if not plan:
                    plan = TenantPlan.objects.filter(
                        slug="free", is_active=True,
                    ).first()
                    if not plan:
                        raise NotFoundError(
                            "No FREE plan found. "
                            "Run: manage.py seed_default_plans",
                            code="PLAN_NOT_FOUND",
                        )

            # Get limit from plan (or 0 when no ML plan)
            if plan is None:
                max_limit = 0
            else:
                max_limit = plan.get_limit(limit_key)

            # Query current usage from the resource counter registry.
            # This count is authoritative — it runs inside the lock scope.
            current_usage = get_resource_count(tenant_id, limit_key)

            # For storage limits, the counter returns bytes and delta is
            # also in bytes; convert both to GB for comparison against the
            # limit (which is specified in GB in the plan).
            if limit_key in ("max_storage_gb", "max_ml_storage_gb") and max_limit is not None:
                current_usage_for_comparison = current_usage / (1024**3)
                delta_for_comparison = delta / (1024**3)
            else:
                current_usage_for_comparison = current_usage
                delta_for_comparison = delta

            plan_slug = plan.slug if plan else "none"
            plan_tier = plan.tier if plan else "NONE"

            # If max_limit is None, it means unlimited (typically for ENTERPRISE)
            if max_limit is None:
                return {
                    "allowed": True,
                    "current": current_usage,
                    "max": None,
                    "remaining": None,
                    "limit_key": limit_key,
                    "plan_slug": plan_slug,
                    "plan_tier": plan_tier,
                }

            # Calculate new usage with delta
            new_usage = current_usage_for_comparison + delta_for_comparison

            # Check if limit exceeded
            if new_usage > max_limit:
                raise ValidationError(
                    f"Plan limit exceeded for {limit_key}",
                    code="plan_limit_exceeded",
                    details={
                        "limit_key": limit_key,
                        "current": current_usage,
                        "max": max_limit,
                        "requested_delta": delta,
                        "new_usage": new_usage,
                        "plan_slug": plan_slug,
                        "plan_tier": plan_tier,
                    },
                    http_status=403,
                )

            # Calculate remaining
            remaining = max_limit - new_usage

            return {
                "allowed": True,
                "current": current_usage,
                "max": max_limit,
                "remaining": remaining,
                "limit_key": limit_key,
                "plan_slug": plan_slug,
                "plan_tier": plan_tier,
            }

        return self.execute_with_transaction(operation="check_limit", tenant_id=tenant_id, func=_check)


class TenantUsageService(BaseService):
    """
    Service for aggregating and retrieving tenant usage summaries.

    Provides business logic for:
    - Calculating usage summaries for a period
    - Retrieving current usage
    - Aggregating metrics for billing/admin
    """

    service_name = "tenant_usage_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize TenantUsageService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID
        """
        super().__init__(tenant_id=tenant_id, user_id=user_id)

    def calculate_usage_summary(
        self,
        tenant_id: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> TenantUsageSummary:
        """
        Calculate usage summary for a tenant for a given period.

        Args:
            tenant_id: Tenant ID
            period_start: Start of period (defaults to start of current month)
            period_end: End of period (defaults to end of current month)

        Returns:
            TenantUsageSummary instance (created or updated)
        """

        def _calculate():
            tenant = self.get_resource_or_raise(Tenant, tenant_id)

            # Default to current month if not specified
            # Use local variables to avoid shadowing function parameters
            local_period_start = period_start
            local_period_end = period_end

            if not local_period_start:
                now = timezone.now()
                local_period_start = datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
            if not local_period_end:
                # End of current month
                if local_period_start.month == 12:
                    local_period_end = datetime(
                        local_period_start.year + 1, 1, 1, tzinfo=local_period_start.tzinfo
                    ) - timedelta(seconds=1)
                else:
                    local_period_end = datetime(
                        local_period_start.year,
                        local_period_start.month + 1,
                        1,
                        tzinfo=local_period_start.tzinfo,
                    ) - timedelta(seconds=1)

            # Get or create usage summary
            usage_summary, created = TenantUsageSummary.objects.get_or_create(
                tenant=tenant,
                period_start=local_period_start,
                period_end=local_period_end,
                defaults={},
            )

            # Calculate API calls count (from BaaS APIUsage or audit events)
            from hub.apps.baas.models import APIKey, APIUsage

            api_keys = APIKey.objects.filter(tenant_id=tenant_id)
            api_calls_count = APIUsage.objects.filter(
                api_key__in=api_keys,
                timestamp__gte=local_period_start,
                timestamp__lte=local_period_end,
            ).count()

            # Get current asset count
            from hub.apps.assets.models import Asset

            asset_count = Asset.objects.filter(tenant_id=tenant_id).count()

            # Get current dataset count
            from hub.apps.datasets.models import Dataset

            dataset_count = Dataset.objects.filter(tenant_id=tenant_id).count()

            # Get scheduled ingestion runs count
            from hub.apps.scheduled_ingestion.models import ScheduledIngestionRun

            scheduled_ingestion_runs_count = ScheduledIngestionRun.objects.filter(
                scheduled_ingestion__tenant_id=tenant_id,
                created_at__gte=local_period_start,
                created_at__lte=local_period_end,
            ).count()

            # Get scheduled export runs count
            from hub.apps.scheduled_export.models import ScheduledExportRun

            scheduled_export_runs_count = ScheduledExportRun.objects.filter(
                scheduled_export__tenant_id=tenant_id,
                created_at__gte=local_period_start,
                created_at__lte=local_period_end,
            ).count()

            # Calculate storage bytes (from File model)
            from hub.apps.files.models import File, FileStatus

            storage_result = File.objects.filter(
                tenant_id=tenant_id, status=FileStatus.ACTIVE
            ).aggregate(total_size=Sum("size"))
            storage_bytes = storage_result["total_size"] or 0

            # Aggregate ingestion cost from existing IngestionCost records (created when runs complete).
            # Do NOT call CostTrackingManager.calculate_run_costs here—that would create duplicates.
            ingestion_cost = None
            try:
                from hub.apps.scheduled_ingestion.models import IngestionCost

                ingestion_total = IngestionCost.objects.filter(
                    scheduled_ingestion__tenant_id=tenant_id,
                    period_start__gte=local_period_start,
                    period_end__lte=local_period_end,
                ).aggregate(total=Sum("total_cost_usd"))["total"]
                if ingestion_total is not None and ingestion_total > 0:
                    ingestion_cost = ingestion_total
            except (ImportError, LookupError):
                # Cost tracking module may not be available, skip
                pass

            # Update usage summary
            usage_summary.api_calls_count = api_calls_count
            usage_summary.asset_count = asset_count
            usage_summary.dataset_count = dataset_count
            usage_summary.scheduled_ingestion_runs_count = scheduled_ingestion_runs_count
            usage_summary.scheduled_export_runs_count = scheduled_export_runs_count
            usage_summary.storage_bytes = storage_bytes
            usage_summary.ingestion_cost = ingestion_cost
            usage_summary.save()

            return usage_summary

        return self.execute_with_metrics(
            operation="calculate_usage_summary", tenant_id=tenant_id, func=_calculate
        )

    def get_current_usage(self, tenant_id: str) -> Dict[str, Any]:
        """
        Phase 277.B.106 — dynamic RESOURCE_COUNTERS usage.

        Iterates every counter in ``RESOURCE_COUNTERS`` so all 30+
        ``KNOWN_LIMIT_KEYS`` return real usage data instead of zero.
        Cached in Redis for 60 s (30+ COUNT queries per uncached call).

        Args:
            tenant_id: Tenant ID

        Returns:
            Dictionary with ``{limit_key}_usage`` entries for every
            registered counter, plus ``quota_warnings`` for >=80%.
        """

        def _get_current():
            from django.core.cache import cache as _cache

            cache_key = f"tenant_usage:{tenant_id}"
            cached = _cache.get(cache_key)
            if cached is not None:
                return cached

            from hub.apps.billing.limit_registry import RESOURCE_COUNTERS, get_resource_count

            usage: dict[str, Any] = {"tenant_id": str(tenant_id)}

            for limit_key in sorted(RESOURCE_COUNTERS.keys()):
                try:
                    count_or_size = get_resource_count(tenant_id, limit_key)
                except Exception:
                    count_or_size = 0
                # Normalise limit_key → usage key: max_assets → asset_usage
                usage_key = limit_key.replace("max_", "") + "_usage"
                usage[usage_key] = count_or_size

            _cache.set(cache_key, usage, timeout=60)
            return usage

        return self.execute_with_metrics(
            operation="get_current_usage", tenant_id=tenant_id, func=_get_current
        )

    def get_usage_summary(
        self,
        tenant_id: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> TenantUsageSummary:
        """
        Get or calculate usage summary for a period.

        Args:
            tenant_id: Tenant ID
            period_start: Start of period (defaults to start of current month)
            period_end: End of period (defaults to end of current month)

        Returns:
            TenantUsageSummary instance
        """
        # Calculate if doesn't exist or is stale
        return self.calculate_usage_summary(tenant_id, period_start, period_end)


class TenantOnboardingService(BaseService, TenantEventPublisher):
    """
    Service for self-service tenant onboarding.

    Provides business logic for:
    - Creating tenant with first user
    - Assigning default plan (FREE)
    - Creating Stripe customer and FREE subscription
    - Creating TenantConfig with defaults
    """

    service_name = "tenant_onboarding_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize TenantOnboardingService.

        Args:
            tenant_id: Optional tenant ID (not used for onboarding)
            user_id: Optional user ID (not used for onboarding)
        """
        self.tenant_id = tenant_id
        self.user_id = user_id
        TenantEventPublisher.__init__(self, tenant_id=tenant_id, user_id=user_id)

    @transaction.atomic
    def create_tenant_with_first_user(
        self,
        name: str,
        slug: str,
        plan_slug: str = "free",
        first_user_email: str = None,
        first_user_password: str = None,
        first_user_display_name: str = None,
        region: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a tenant with first user (self-service onboarding).

        Args:
            name: Tenant name
            slug: Tenant slug (URL-safe identifier)
            plan_slug: Plan slug (defaults to 'free')
            first_user_email: Email for first user (tenant admin)
            first_user_password: Password for first user
            first_user_display_name: Display name for first user
            region: Optional cloud region

        Returns:
            Dictionary with tenant, user, and subscription information

        Raises:
            ValidationError: If creation fails
        """

        def _create():
            import logging

            from hub.apps.billing.services import SubscriptionService
            from hub.apps.tenants.models import TenantConfig
            from hub.apps.tenants.validators import get_platform_defaults
            from hub.apps.users.models import Role, User, UserRole, UserStatus

            logger = logging.getLogger(__name__)

            # Validate inputs
            if not first_user_email:
                raise ValidationError("first_user_email is required")
            if not first_user_password:
                raise ValidationError("first_user_password is required")

            # Get plan
            try:
                plan = TenantPlan.objects.get(slug=plan_slug, is_active=True)
            except TenantPlan.DoesNotExist:
                raise NotFoundError(f"Plan with slug '{plan_slug}' not found")

            # Create tenant (nested atomic block acts as savepoint)
            try:
                with transaction.atomic():
                    tenant = Tenant.objects.create(
                        name=name,
                        slug=slug,
                        region=region,
                        status=TenantStatus.ACTIVE,
                        kyc_status=KYCStatus.UNVERIFIED,
                        plan=plan,
                        # Phase 250.6.D.1 (closes G2-1 / P2-1) — new
                        # tenants START with the asset-creation gate
                        # CLOSED. The post_save signal handlers in
                        # ``tenants.signals`` watch the three onboarding
                        # signals (TENANT_ADMIN role grant, KYC submission,
                        # active Subscription) and call
                        # ``mark_onboarding_complete_if_ready`` which
                        # atomically sets ``onboarding_completed_at`` AND
                        # flips this flag back to True. Existing tenants
                        # are unaffected — the migration's DB-level
                        # default for the field is True, and the
                        # backfill stamps existing onboarded tenants
                        # so they appear "complete" immediately.
                        asset_creation_enabled=False,
                    )
            except IntegrityError:
                raise ValidationError(
                    f"Tenant with slug '{slug}' or name '{name}' already exists",
                    code="SLUG_EXISTS",
                )

            # Create first user (nested atomic block acts as savepoint)
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        email=first_user_email,
                        password=first_user_password,
                        tenant=tenant,
                        display_name=first_user_display_name or (
                            first_user_email.split("@")[0] if "@" in first_user_email else first_user_email
                        ),
                        status=UserStatus.ACTIVE,
                    )
            except IntegrityError:
                raise ValidationError(
                    "Email address is already registered",
                    code="EMAIL_EXISTS",
                )

            # Assign TENANT_ADMIN role
            try:
                tenant_admin_role = Role.objects.get(tenant=tenant, name="TENANT_ADMIN")
            except Role.DoesNotExist:
                # Create TENANT_ADMIN role if doesn't exist
                tenant_admin_role = Role.objects.create(
                    tenant=tenant,
                    name="TENANT_ADMIN",
                    description="Tenant administrator with full access",
                )

            UserRole.objects.get_or_create(user=user, role=tenant_admin_role)

            # Create TenantConfig with platform defaults
            platform_defaults = get_platform_defaults()
            TenantConfig.objects.create(
                tenant=tenant,
                default_dq_profile=platform_defaults.get("default_dq_profile"),
                allowed_compliance_regimes=platform_defaults.get("allowed_compliance_regimes", []),
                default_compliance_regimes=platform_defaults.get("default_compliance_regimes", []),
                data_retention_days=platform_defaults.get("data_retention_days"),
                rate_limits=platform_defaults.get("rate_limits", {}),
                max_file_size_bytes=platform_defaults.get("max_file_size_bytes"),
                max_job_concurrency=platform_defaults.get("max_job_concurrency"),
                max_queued_jobs=platform_defaults.get("max_queued_jobs"),
            )

            # Create Stripe customer and subscription
            subscription = None
            if plan.tier != "FREE":
                try:
                    subscription_service = SubscriptionService()
                    customer_result = subscription_service.create_customer(
                        tenant=tenant, email=first_user_email
                    )
                    subscription = subscription_service.create_subscription(
                        tenant=tenant, plan=plan, trial_days=14 if plan.tier == "PRO" else 0
                    )
                except Exception as e:
                    # Log error but don't fail tenant creation
                    logger.warning(
                        "stripe_subscription_creation_failed_during_onboarding",
                        tenant_id=str(tenant.id),
                        error=str(e),
                        message=f"Failed to create Stripe subscription during onboarding: {e}",
                    )
            else:
                # For FREE plan, create a subscription record without Stripe
                from hub.apps.billing.models import Subscription, SubscriptionStatus

                subscription = Subscription.objects.create(
                    tenant=tenant,
                    plan=plan,
                    status=SubscriptionStatus.ACTIVE,
                    current_period_start=timezone.now(),
                    current_period_end=timezone.now()
                    + timedelta(days=365 * 100),  # Effectively forever
                )

            # Publish tenant.created event
            self.publish_tenant_created(
                tenant_id=str(tenant.id),
                name=tenant.name,
                slug=tenant.slug,
                status=tenant.status,
                kyc_status=tenant.kyc_status,
                region=tenant.region,
            )

            # Log audit events
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(
                resource_type="TENANT",
                action="TENANT_CREATED",
                tenant=tenant,
                actor_user=user,
                resource_id=str(tenant.id),
                details={
                    "name": tenant.name,
                    "slug": tenant.slug,
                    "plan_slug": plan.slug,
                    "self_service": True,
                },
            )

            create_audit_event(
                resource_type="USER",
                action="USER_CREATED",
                tenant=tenant,
                actor_user=user,
                resource_id=str(user.id),
                details={
                    "email": user.email,
                    "display_name": user.display_name,
                    "role": "TENANT_ADMIN",
                    "self_service_onboarding": True,
                },
            )

            return {"tenant": tenant, "user": user, "subscription": subscription, "plan": plan}

        return self.execute_with_metrics(
            operation="create_tenant_with_first_user",
            tenant_id=None,  # No tenant_id yet
            func=_create,
        )


class PersonalTenantService(BaseService, TenantEventPublisher):
    """
    Service for creating personal tenants for self-service registration.

    Creates a tenant with FREE plan, TenantConfig, Subscription, and
    DATA_PROVIDER/DATA_CONSUMER roles when a user registers without tenant_id.
    Publishes tenant.created event for consistency with other tenant creation flows.
    """

    service_name = "personal_tenant_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """Initialize PersonalTenantService."""
        self.tenant_id = tenant_id
        self.user_id = user_id
        TenantEventPublisher.__init__(self, tenant_id=tenant_id, user_id=user_id)

    @transaction.atomic
    def create_personal_tenant_for_user(
        self, email: str, display_name: Optional[str] = None
    ) -> Tenant:
        """
        Create a personal tenant for a user (self-service registration).

        Creates Tenant (name="Personal - {email}", slug="personal-{uuid8}"),
        assigns FREE plan, creates TenantConfig with platform defaults,
        creates Subscription (ACTIVE), and creates DATA_PROVIDER and DATA_CONSUMER roles.
        Publishes tenant.created event.

        Args:
            email: User email (used for tenant name)
            display_name: Optional display name (unused; reserved for future use)

        Returns:
            Created Tenant instance

        Raises:
            NotFoundError: If FREE plan does not exist (run seed_default_plans)
        """
        from django.db import IntegrityError

        from hub.apps.billing.models import Subscription, SubscriptionStatus
        from hub.apps.users.models import Role

        def _create() -> Tenant:
            # Get FREE plan; raise clear error if missing
            try:
                plan = TenantPlan.objects.get(slug="free", is_active=True)
            except TenantPlan.DoesNotExist:
                raise NotFoundError(
                    "FREE plan not found. Run 'python manage.py seed_default_plans' to create default plans.",
                    code="PLAN_NOT_FOUND",
                    details={"required_plan": "free"},
                )

            name = f"Personal - {email}"
            max_slug_attempts = 5
            tenant = None

            for _ in range(max_slug_attempts):
                slug = f"personal-{uuid.uuid4().hex[:8]}"
                try:
                    with transaction.atomic():
                        tenant = Tenant.objects.create(
                            name=name,
                            slug=slug,
                            region=None,
                            status=TenantStatus.ACTIVE,
                            kyc_status=KYCStatus.UNVERIFIED,
                            plan=plan,
                        )
                    break
                except IntegrityError:
                    tenant = None
                    continue

            if tenant is None:
                raise ValidationError(
                    "Registration failed. Please try again.",
                    code="TENANT_CREATE_COLLISION",
                )

            self.publish_tenant_created(
                tenant_id=str(tenant.id),
                name=tenant.name,
                slug=tenant.slug,
                status=tenant.status,
                kyc_status=tenant.kyc_status,
                region=tenant.region,
            )

            platform_defaults = get_platform_defaults()
            TenantConfig.objects.create(
                tenant=tenant,
                default_dq_profile=platform_defaults.get("default_dq_profile"),
                allowed_compliance_regimes=platform_defaults.get("allowed_compliance_regimes", []),
                default_compliance_regimes=platform_defaults.get("default_compliance_regimes", []),
                data_retention_days=platform_defaults.get("data_retention_days"),
                rate_limits=platform_defaults.get("rate_limits", {}),
                max_file_size_bytes=platform_defaults.get("max_file_size_bytes"),
                max_job_concurrency=platform_defaults.get("max_job_concurrency"),
                max_queued_jobs=platform_defaults.get("max_queued_jobs"),
            )

            Subscription.objects.create(
                tenant=tenant,
                plan=plan,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=timezone.now(),
                current_period_end=timezone.now() + timedelta(days=365 * 100),
            )

            for role_name, description in [
                ("DATA_PROVIDER", "Can create and manage data assets"),
                ("DATA_CONSUMER", "Can consume and purchase data products"),
            ]:
                Role.objects.get_or_create(
                    tenant=tenant,
                    name=role_name,
                    defaults={"description": description},
                )

            return tenant

        return self.execute_with_metrics(
            operation="create_personal_tenant_for_user",
            tenant_id=None,
            func=_create,
        )


class TenantLifecycleService(BaseService, TenantEventPublisher):
    """
    Service for tenant lifecycle management (suspend, resume).

    Provides business logic for:
    - Suspending tenants (read-only mode)
    - Resuming suspended tenants
    - Emitting audit events
    """

    service_name = "tenant_lifecycle_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize TenantLifecycleService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID (actor performing the action)
        """
        self.tenant_id = tenant_id
        self.user_id = user_id
        TenantEventPublisher.__init__(self, tenant_id=tenant_id, user_id=user_id)

    @transaction.atomic
    def suspend_tenant(self, tenant_id: str, reason: Optional[str] = None) -> Tenant:
        """
        Suspend a tenant (read-only mode).

        Args:
            tenant_id: Tenant ID to suspend
            reason: Optional reason for suspension

        Returns:
            Suspended Tenant instance

        Raises:
            NotFoundError: If tenant not found
            ValidationError: If tenant is already deleted
        """

        def _suspend():
            tenant = self.get_resource_or_raise(Tenant, tenant_id)

            if tenant.status == TenantStatus.DELETED:
                raise ValidationError("Cannot suspend a deleted tenant", code="TENANT_DELETED")

            if tenant.status == TenantStatus.SUSPENDED:
                # Already suspended, return as-is
                return tenant

            # Suspend tenant
            tenant.suspend()

            # Log audit event
            from hub.apps.audit.utils import create_audit_event
            from hub.apps.users.models import User

            actor_user = None
            if self.user_id:
                try:
                    actor_user = User.objects.get(id=self.user_id)
                except User.DoesNotExist:
                    pass

            create_audit_event(
                resource_type="TENANT",
                action="TENANT_SUSPENDED",
                tenant=tenant,
                actor_user=actor_user,
                resource_id=str(tenant.id),
                details={
                    "reason": reason,
                    "previous_status": TenantStatus.ACTIVE,
                    "new_status": TenantStatus.SUSPENDED,
                },
            )

            return tenant

        return self.execute_with_metrics(
            operation="suspend_tenant", tenant_id=tenant_id, func=_suspend
        )

    @transaction.atomic
    def resume_tenant(self, tenant_id: str) -> Tenant:
        """
        Resume a suspended tenant.

        Args:
            tenant_id: Tenant ID to resume

        Returns:
            Resumed Tenant instance

        Raises:
            NotFoundError: If tenant not found
            ValidationError: If tenant is not suspended
        """

        def _resume():
            tenant = self.get_resource_or_raise(Tenant, tenant_id)

            if tenant.status != TenantStatus.SUSPENDED:
                raise ValidationError(
                    "Can only resume suspended tenants",
                    code="TENANT_NOT_SUSPENDED",
                    details={"current_status": tenant.status},
                )

            # Resume tenant
            tenant.reactivate()

            # Log audit event
            from hub.apps.audit.utils import create_audit_event
            from hub.apps.users.models import User

            actor_user = None
            if self.user_id:
                try:
                    actor_user = User.objects.get(id=self.user_id)
                except User.DoesNotExist:
                    pass

            create_audit_event(
                resource_type="TENANT",
                action="TENANT_REACTIVATED",
                tenant=tenant,
                actor_user=actor_user,
                resource_id=str(tenant.id),
                details={
                    "previous_status": TenantStatus.SUSPENDED,
                    "new_status": TenantStatus.ACTIVE,
                },
            )

            return tenant

        return self.execute_with_metrics(
            operation="resume_tenant", tenant_id=tenant_id, func=_resume
        )
