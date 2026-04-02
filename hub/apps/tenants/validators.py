"""
Tenant Configuration Validators

Validators for TenantConfig fields.
"""
from django.core.exceptions import ValidationError
from typing import List, Dict, Any


# Platform-supported DQ profiles
VALID_DQ_PROFILES = [
    "intake_basic_gx",
    "intake_basic_soda",
]

# Platform-supported compliance regimes
# Mirrors the canonical regulation keys in services/compliance-service/regulations/
VALID_COMPLIANCE_REGIMES = [
    # EU / UK
    "GDPR",
    "GDPR_SCHREMS_II",
    "UK_GDPR",
    # Americas
    "LGPD",
    "CCPA",
    "COPPA",
    "FERPA",
    "GLBA",
    "HIPAA",
    "SOX",
    "PIPEDA",
    # US state privacy laws
    "CPA",
    "CTDPA",
    "ICDPA",
    "MCDPA",
    "MHMDA",
    "MTCDPA",
    "NHPA",
    "NJDPA",
    "OCPA",
    "TDPSA",
    "TIPA",
    "UCPA",
    "VCDPA",
    # APAC
    "APPI_JP",
    "DPDP_IN",
    "PDPA_SG",
    "PIPA_KR",
    "PIPL_CN",
    "PRIVACY_ACT_AU",
    # Africa
    "POPIA_ZA",
    # Industry
    "PCI_DSS",
]

# Platform maximum rate limits (per category)
PLATFORM_MAX_RATE_LIMITS = {
    "dq_runs": {
        "burst_per_10s": 100,
        "sustained_per_min": 300,
        "daily_cap": 100000,
    },
    "compliance_runs": {
        "burst_per_10s": 100,
        "sustained_per_min": 300,
        "daily_cap": 100000,
    },
    "file_uploads": {
        "burst_per_10s": 50,
        "sustained_per_min": 150,
    },
    "contract_validation": {
        "burst_per_10s": 100,
        "sustained_per_min": 300,
    },
    "catalog_reads": {
        "burst_per_10s": 200,
        "sustained_per_min": 1000,
    },
    "sparql_queries": {
        "burst_per_10s": 50,
        "sustained_per_min": 200,
    },
}


def validate_dq_profile(value: str) -> None:
    """
    Validate that DQ profile is a valid profile key.
    
    Args:
        value: DQ profile key
        
    Raises:
        ValidationError: If profile key is invalid
    """
    if value and value not in VALID_DQ_PROFILES:
        raise ValidationError(
            f"Invalid DQ profile key: {value}. Valid profiles are: {', '.join(VALID_DQ_PROFILES)}"
        )


def validate_compliance_regimes(value: List[str]) -> None:
    """
    Validate that compliance regimes are valid and supported by platform.
    
    Args:
        value: List of compliance regime codes
        
    Raises:
        ValidationError: If any regime is invalid
    """
    if not isinstance(value, list):
        raise ValidationError("Compliance regimes must be a list")
    
    invalid_regimes = [r for r in value if r not in VALID_COMPLIANCE_REGIMES]
    if invalid_regimes:
        raise ValidationError(
            f"Invalid compliance regimes: {', '.join(invalid_regimes)}. "
            f"Valid regimes are: {', '.join(VALID_COMPLIANCE_REGIMES)}"
        )


def validate_rate_limits(value: Dict[str, Any]) -> None:
    """
    Validate that rate limits do not exceed platform maximums.
    
    Rate limits structure:
    {
        "category_name": {
            "burst_per_10s": int,      # Optional: requests per 10 seconds
            "sustained_per_min": int,  # Optional: requests per minute
            "daily_cap": int           # Optional: requests per day (only for some categories)
        }
    }
    
    Valid categories: dq_runs, compliance_runs, file_uploads, contract_validation,
                     catalog_reads, sparql_queries
    
    Each category must have at least one limit specified. Limits cannot exceed
    platform maximums defined in PLATFORM_MAX_RATE_LIMITS.
    
    Args:
        value: Rate limits dictionary with category keys and limit dictionaries
        
    Raises:
        ValidationError: If rate limits exceed platform maximums or invalid category
    """
    if not isinstance(value, dict):
        raise ValidationError("Rate limits must be a dictionary")
    
    for category, limits in value.items():
        if category not in PLATFORM_MAX_RATE_LIMITS:
            raise ValidationError(
                f"Invalid rate limit category: {category}. "
                f"Valid categories are: {', '.join(PLATFORM_MAX_RATE_LIMITS.keys())}"
            )
        
        platform_max = PLATFORM_MAX_RATE_LIMITS[category]
        
        # Check burst_per_10s
        if "burst_per_10s" in limits:
            if limits["burst_per_10s"] > platform_max.get("burst_per_10s", float("inf")):
                raise ValidationError(
                    f"Rate limit {category}.burst_per_10s ({limits['burst_per_10s']}) "
                    f"exceeds platform maximum ({platform_max.get('burst_per_10s')})"
                )
        
        # Check sustained_per_min
        if "sustained_per_min" in limits:
            if limits["sustained_per_min"] > platform_max.get("sustained_per_min", float("inf")):
                raise ValidationError(
                    f"Rate limit {category}.sustained_per_min ({limits['sustained_per_min']}) "
                    f"exceeds platform maximum ({platform_max.get('sustained_per_min')})"
                )
        
        # Check daily_cap (if applicable)
        if "daily_cap" in limits:
            if "daily_cap" not in platform_max:
                raise ValidationError(
                    f"Rate limit category {category} does not support daily_cap"
                )
            if limits["daily_cap"] > platform_max.get("daily_cap", float("inf")):
                raise ValidationError(
                    f"Rate limit {category}.daily_cap ({limits['daily_cap']}) "
                    f"exceeds platform maximum ({platform_max.get('daily_cap')})"
                )


def get_platform_defaults() -> Dict[str, Any]:
    """
    Get platform default configuration values.
    
    Returns a new dictionary with platform default values. The dictionary is
    created fresh on each call to ensure immutability (modifications to the
    returned dict do not affect subsequent calls).
    
    Platform defaults are used when tenant-specific configuration is not set
    or when fields are null/empty.
    
    Returns:
        Dictionary with platform default values including:
        - default_dq_profile: "intake_basic_gx"
        - allowed_compliance_regimes: All supported regimes
        - default_compliance_regimes: ["GDPR", "LGPD"]
        - data_retention_days: 2555 (7 years)
        - rate_limits: Platform defaults per category
        - max_file_size_bytes: 10737418240 (10 GB)
        - max_job_concurrency: 5
        - max_queued_jobs: 50
    """
    return {
        "default_dq_profile": "intake_basic_gx",
        "allowed_compliance_regimes": list(VALID_COMPLIANCE_REGIMES),
        "default_compliance_regimes": ["GDPR", "LGPD"],
        "data_retention_days": 2555,  # 7 years
        "rate_limits": {
            "dq_runs": {
                "burst_per_10s": 20,
                "sustained_per_min": 60,
                "daily_cap": 10000,
            },
            "compliance_runs": {
                "burst_per_10s": 20,
                "sustained_per_min": 60,
                "daily_cap": 10000,
            },
            "file_uploads": {
                "burst_per_10s": 10,
                "sustained_per_min": 30,
            },
            "contract_validation": {
                "burst_per_10s": 20,
                "sustained_per_min": 60,
            },
            "catalog_reads": {
                "burst_per_10s": 50,
                "sustained_per_min": 200,
            },
            "sparql_queries": {
                "burst_per_10s": 50,
                "sustained_per_min": 200,
            },
        },
        "max_file_size_bytes": 10737418240,  # 10 GB
        "max_job_concurrency": 5,
        "max_queued_jobs": 50,
        "trust_signals_enabled": True,
        "versioning_enabled": True,
        "workflows_enabled": True,
    }

