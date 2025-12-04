"""
Tenant Configuration Services

Services for resolving tenant configuration with platform defaults.
"""
from typing import Dict, Any, Optional
from django.core.exceptions import ObjectDoesNotExist
from .models import Tenant, TenantConfig
from .validators import get_platform_defaults


def get_tenant_config(tenant: Tenant) -> Dict[str, Any]:
    """
    Get tenant configuration with platform defaults.
    
    Returns a dictionary with all configuration values, using platform defaults
    for any values not set in the tenant's configuration.
    
    Merge behavior:
    - None values are replaced with platform defaults
    - Empty lists [] are treated as falsy and use platform defaults
    - Empty dict {} for rate_limits uses platform defaults
    - Non-empty values override platform defaults
    
    Rate limits merge: If tenant has partial rate_limits (only some categories),
    the result includes tenant-specific categories merged with platform defaults
    for missing categories.
    
    Args:
        tenant: Tenant instance
        
    Returns:
        Dictionary with complete configuration (tenant values + platform defaults)
        matching API spec §13.1 format with fields:
        - tenant_id: UUID string
        - default_dq_profile: string or platform default
        - allowed_compliance_regimes: list or platform default
        - default_compliance_regimes: list or platform default
        - data_retention_days: int or platform default
        - rate_limits: dict (merged tenant + platform defaults)
        - max_file_size_bytes: int or platform default
        - max_job_concurrency: int or platform default
        - max_queued_jobs: int or platform default
        - created_at: ISO 8601 timestamp string or None
        - updated_at: ISO 8601 timestamp string or None
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
    # Rate limits: Merge tenant-specific categories with platform defaults
    # If tenant has partial rate_limits, merge categories (tenant overrides platform for same category)
    tenant_rate_limits = config.rate_limits if config.rate_limits else {}
    merged_rate_limits = platform_defaults["rate_limits"].copy()
    merged_rate_limits.update(tenant_rate_limits)  # Tenant categories override platform defaults
    
    result = {
        "tenant_id": str(tenant.id),
        "default_dq_profile": config.default_dq_profile or platform_defaults["default_dq_profile"],
        "allowed_compliance_regimes": config.allowed_compliance_regimes or platform_defaults["allowed_compliance_regimes"],
        "default_compliance_regimes": config.default_compliance_regimes or platform_defaults["default_compliance_regimes"],
        "data_retention_days": config.data_retention_days if config.data_retention_days is not None else platform_defaults["data_retention_days"],
        "rate_limits": merged_rate_limits,  # Merged: tenant categories + platform defaults
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
        key: Configuration key (e.g., 'default_dq_profile', 'max_file_size_bytes')
        default: Optional custom default value (overrides platform default if provided)
        
    Returns:
        Configuration value. If key exists in config_dict, returns that value.
        If key doesn't exist and default is provided, returns default.
        Otherwise returns None.
    """
    config_dict = get_tenant_config(tenant)
    # If key exists in config_dict, return it (could be tenant value or platform default)
    if key in config_dict:
        # If a custom default is provided, it should override platform default
        # This allows callers to provide their own default instead of platform default
        if default is not None:
            return default
        return config_dict[key]
    # Key doesn't exist, return custom default or None
    return default


def get_tenant_dq_profile(tenant_id: str) -> str:
    """
    Get tenant DQ profile with platform default fallback.
    
    Priority:
    1. Tenant-specific default_dq_profile from TenantConfig
    2. Platform default (intake_basic_gx)
    
    Args:
        tenant_id: Tenant UUID as string
        
    Returns:
        DQ profile key (e.g., 'intake_basic_gx', 'intake_basic_soda')
    """
    from .models import Tenant
    import uuid
    
    try:
        tenant = Tenant.objects.get(id=uuid.UUID(tenant_id))
        config_dict = get_tenant_config(tenant)
        return config_dict.get("default_dq_profile", "intake_basic_gx")
    except (Tenant.DoesNotExist, ValueError):
        # If tenant doesn't exist, return platform default
        platform_defaults = get_platform_defaults()
        return platform_defaults.get("default_dq_profile", "intake_basic_gx")


def get_tenant_compliance_regimes(tenant_id: str) -> list:
    """
    Get tenant default compliance regimes with platform default fallback.
    
    Priority:
    1. Tenant-specific default_compliance_regimes from TenantConfig
    2. Platform default (['GDPR', 'LGPD'])
    
    Args:
        tenant_id: Tenant UUID as string
        
    Returns:
        List of compliance regime codes (e.g., ['GDPR', 'LGPD'])
    """
    from .models import Tenant
    import uuid
    
    try:
        tenant = Tenant.objects.get(id=uuid.UUID(tenant_id))
        config_dict = get_tenant_config(tenant)
        return config_dict.get("default_compliance_regimes", ["GDPR", "LGPD"])
    except (Tenant.DoesNotExist, ValueError):
        # If tenant doesn't exist, return platform default
        platform_defaults = get_platform_defaults()
        return platform_defaults.get("default_compliance_regimes", ["GDPR", "LGPD"])


def get_tenant_file_size_limit(tenant_id: str) -> int:
    """
    Get tenant file size limit with platform default fallback.
    
    Priority:
    1. Tenant-specific max_file_size_bytes from TenantConfig
    2. Platform default (10737418240 bytes = 10 GB)
    
    Args:
        tenant_id: Tenant UUID as string
        
    Returns:
        Maximum file size in bytes
    """
    from .models import Tenant
    import uuid
    
    try:
        tenant = Tenant.objects.get(id=uuid.UUID(tenant_id))
        config_dict = get_tenant_config(tenant)
        return config_dict.get("max_file_size_bytes", 10737418240)
    except (Tenant.DoesNotExist, ValueError):
        # If tenant doesn't exist, return platform default
        platform_defaults = get_platform_defaults()
        return platform_defaults.get("max_file_size_bytes", 10737418240)


def get_tenant_job_limits(tenant_id: str) -> Dict[str, int]:
    """
    Get tenant job concurrency and queuing limits with platform default fallback.
    
    Priority:
    1. Tenant-specific max_job_concurrency and max_queued_jobs from TenantConfig
    2. Platform defaults (max_job_concurrency=5, max_queued_jobs=50)
    
    Args:
        tenant_id: Tenant UUID as string
        
    Returns:
        Dictionary with keys:
        - max_job_concurrency: Maximum concurrent running jobs
        - max_queued_jobs: Maximum queued jobs
    """
    from .models import Tenant
    import uuid
    
    try:
        tenant = Tenant.objects.get(id=uuid.UUID(tenant_id))
        config_dict = get_tenant_config(tenant)
        return {
            "max_job_concurrency": config_dict.get("max_job_concurrency", 5),
            "max_queued_jobs": config_dict.get("max_queued_jobs", 50),
        }
    except (Tenant.DoesNotExist, ValueError):
        # If tenant doesn't exist, return platform defaults
        platform_defaults = get_platform_defaults()
        return {
            "max_job_concurrency": platform_defaults.get("max_job_concurrency", 5),
            "max_queued_jobs": platform_defaults.get("max_queued_jobs", 50),
        }

