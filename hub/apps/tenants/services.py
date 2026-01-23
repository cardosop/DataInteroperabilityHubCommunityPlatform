"""
Tenant Service

Business logic for tenant operations.
"""
from typing import Dict, Any, Optional
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from hub.apps.core.services.base import BaseService, ValidationError, NotFoundError, PermissionError
from hub.apps.core.events.service_publishers import TenantEventPublisher
from hub.apps.tenants.models import Tenant, TenantStatus, TenantConfig, KYCStatus
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
        "default_dq_profile": config.default_dq_profile if config.default_dq_profile else platform_defaults["default_dq_profile"],
        # For JSONField lists, they're never None (have default=default_empty_list), so return the actual saved value
        "allowed_compliance_regimes": config.allowed_compliance_regimes,
        "default_compliance_regimes": config.default_compliance_regimes,
        "data_retention_days": config.data_retention_days if config.data_retention_days is not None else platform_defaults["data_retention_days"],
        "rate_limits": merged_rate_limits,
        "max_file_size_bytes": config.max_file_size_bytes if config.max_file_size_bytes is not None else platform_defaults["max_file_size_bytes"],
        "max_job_concurrency": config.max_job_concurrency if config.max_job_concurrency is not None else platform_defaults["max_job_concurrency"],
        "max_queued_jobs": config.max_queued_jobs if config.max_queued_jobs is not None else platform_defaults["max_queued_jobs"],
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

    def get_tenant(
        self,
        tenant_id: str
    ) -> Tenant:
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
            func=lambda: self.get_resource_or_raise(Tenant, tenant_id)
        )

    def validate_kyc_verified(
        self,
        tenant_id: str
    ) -> Tenant:
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
            operation="validate_kyc_verified",
            tenant_id=tenant_id,
            func=_validate
        )

    @transaction.atomic
    def create_tenant(
        self,
        name: str,
        slug: str,
        region: Optional[str] = None,
        **kwargs
    ) -> Tenant:
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
            tenant = Tenant.objects.create(
                name=name,
                slug=slug,
                region=region,
                status=TenantStatus.ACTIVE,
                kyc_status=KYCStatus.UNVERIFIED
            )

            # Publish tenant.created event
            self.publish_tenant_created(
                tenant_id=str(tenant.id),
                name=tenant.name,
                slug=tenant.slug,
                status=tenant.status,
                kyc_status=tenant.kyc_status,
                region=tenant.region,
                **kwargs
            )

            return tenant

        return self.execute_with_metrics(
            operation="create_tenant",
            tenant_id=None,  # No tenant_id yet for creation
            func=_create
        )

    @transaction.atomic
    def update_tenant(
        self,
        tenant_id: str,
        name: Optional[str] = None,
        slug: Optional[str] = None,
        kyc_status: Optional[str] = None,
        region: Optional[str] = None,
        **kwargs
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
                    **kwargs
                )

            return tenant

        return self.execute_with_metrics(
            operation="update_tenant",
            tenant_id=tenant_id,
            func=_update
        )

    @transaction.atomic
    def delete_tenant(
        self,
        tenant_id: str,
        reason: Optional[str] = None,
        **kwargs
    ) -> Tenant:
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
            tenant = self.get_resource_or_raise(Tenant, tenant_id)

            if tenant.status == TenantStatus.DELETED:
                raise ValidationError("Tenant is already deleted")

            # Soft delete tenant
            tenant.soft_delete()

            # Publish tenant.deleted event
            self.publish_tenant_deleted(
                tenant_id=str(tenant.id),
                reason=reason,
                **kwargs
            )

            return tenant

        return self.execute_with_metrics(
            operation="delete_tenant",
            tenant_id=tenant_id,
            func=_delete
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
        **kwargs
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
                            **kwargs
                        )

                        # Force Django to mark the field as changed for JSONField
                        # This ensures the field is included in the save
                        if hasattr(config, '_state'):
                            config._state.adding = False

            # Track rate_limits update
            if rate_limits is not None:
                old_rate_limits = config.rate_limits or {}
                if old_rate_limits != rate_limits:
                    config.rate_limits = rate_limits
                    updated_fields.append('rate_limits')

                    # Publish quota changed event for rate limits
                    self.publish_tenant_quota_changed(
                        tenant_id=str(tenant.id),
                        quota_type="rate_limits",
                        quota_field="rate_limits",
                        previous_value=old_rate_limits,
                        new_value=rate_limits,
                        **kwargs
                    )

            # Save config - always save all fields to ensure JSONField changes are persisted
            # Using update_fields can sometimes cause issues with JSONField, so we save all fields
            config.save()

            # Refresh from database to ensure we have the latest values
            config.refresh_from_db()

            return config

        return self.execute_with_metrics(
            operation="update_tenant_config",
            tenant_id=tenant_id,
            func=_update_config
        )
