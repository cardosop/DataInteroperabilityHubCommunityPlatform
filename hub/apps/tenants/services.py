"""
Tenant Service

Business logic for tenant operations.
"""
from typing import Dict, Any, Optional
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from hub.apps.core.services.base import BaseService, ValidationError, NotFoundError, PermissionError
from hub.apps.tenants.models import Tenant, TenantConfig, KYCStatus
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
        config = tenant.config
    except ObjectDoesNotExist:
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
    
    result = {
        "tenant_id": str(tenant.id),
        "default_dq_profile": config.default_dq_profile or platform_defaults["default_dq_profile"],
        "allowed_compliance_regimes": config.allowed_compliance_regimes or platform_defaults["allowed_compliance_regimes"],
        "default_compliance_regimes": config.default_compliance_regimes or platform_defaults["default_compliance_regimes"],
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
        default: Optional custom default value
        
    Returns:
        Configuration value
    """
    config_dict = get_tenant_config(tenant)
    if key in config_dict:
        return config_dict[key]
    return default


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


class TenantService(BaseService):
    """
    Service for tenant operations.
    
    Provides business logic for retrieving and validating tenants.
    """
    service_name = "tenant_service"
    
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
            func=lambda: self.get_tenant_or_raise(tenant_id)
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
            tenant = self.get_tenant_or_raise(tenant_id)
            
            if tenant.kyc_status != KYCStatus.VERIFIED:
                raise PermissionError(
                    f"Tenant must have VERIFIED KYC status (current: {tenant.kyc_status})",
                    details={"tenant_id": tenant_id, "kyc_status": tenant.kyc_status}
                )
            
            return tenant
        
        return self.execute_with_metrics(
            operation="validate_kyc_verified",
            tenant_id=tenant_id,
            func=_validate
        )
