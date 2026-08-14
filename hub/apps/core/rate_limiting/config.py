"""
Rate Limiting Configuration

Platform default and maximum rate limits per endpoint category.
"""

from django.conf import settings

from hub.apps.core.rate_limiting.utils import EndpointCategory, TimeWindow

# Platform default rate limits per endpoint category
# Structure: {category: {window: limit}}
#
# Rate limits are configured with three time windows:
# - BURST: Short-term burst limit (10 seconds) - allows quick bursts of requests
# - SUSTAINED: Long-term average limit (60 seconds) - prevents sustained abuse
# - DAILY: Daily limit (24 hours) - prevents excessive daily usage
PLATFORM_DEFAULT_LIMITS: dict[str, dict[int, int]] = {
    # Authentication endpoints: 5 requests/minute (strict to prevent brute force)
    EndpointCategory.AUTH: {
        TimeWindow.BURST: 3,  # 3 requests per 10 seconds (allows quick retries)
        TimeWindow.SUSTAINED: 5,  # 5 requests per minute (sustained limit)
        TimeWindow.DAILY: 1000,  # 1,000 requests per day
    },
    # Asset management endpoints: 100 requests/minute
    EndpointCategory.ASSET: {
        TimeWindow.BURST: 20,  # 20 requests per 10 seconds (allows bursts)
        TimeWindow.SUSTAINED: 100,  # 100 requests per minute (sustained limit)
        TimeWindow.DAILY: 50000,  # 50,000 requests per day
    },
    # Contract management endpoints: 100 requests/minute
    EndpointCategory.CONTRACT: {
        TimeWindow.BURST: 20,  # 20 requests per 10 seconds (allows bursts)
        TimeWindow.SUSTAINED: 100,  # 100 requests per minute (sustained limit)
        TimeWindow.DAILY: 50000,  # 50,000 requests per day
    },
    # Search endpoints: 50 requests/minute
    EndpointCategory.SEARCH: {
        TimeWindow.BURST: 10,  # 10 requests per 10 seconds (allows bursts)
        TimeWindow.SUSTAINED: 50,  # 50 requests per minute (sustained limit)
        TimeWindow.DAILY: 20000,  # 20,000 requests per day
    },
    # File upload endpoints: 10 requests/minute (already configured, adjusted to match requirement)
    EndpointCategory.FILE_UPLOAD: {
        TimeWindow.BURST: 3,  # 3 uploads per 10 seconds (allows quick bursts)
        TimeWindow.SUSTAINED: 10,  # 10 uploads per minute (sustained limit)
        TimeWindow.DAILY: 5000,  # 5,000 uploads per day
    },
    EndpointCategory.DQ_RUN: {
        TimeWindow.BURST: 20,  # 20 requests per 10 seconds
        TimeWindow.SUSTAINED: 60,  # 60 requests per minute
        TimeWindow.DAILY: 10000,  # 10,000 requests per day
    },
    EndpointCategory.COMPLIANCE_RUN: {
        TimeWindow.BURST: 20,
        TimeWindow.SUSTAINED: 60,
        TimeWindow.DAILY: 10000,
    },
    EndpointCategory.FILE_DOWNLOAD: {
        TimeWindow.BURST: 50,  # 50 downloads per 10 seconds
        TimeWindow.SUSTAINED: 300,  # 300 downloads per minute
        TimeWindow.DAILY: 50000,  # 50,000 downloads per day
    },
    EndpointCategory.CONTRACT_VALIDATION: {
        TimeWindow.BURST: 30,
        TimeWindow.SUSTAINED: 100,
        TimeWindow.DAILY: 20000,
    },
    EndpointCategory.CATALOG_READ: {
        TimeWindow.BURST: 100,
        TimeWindow.SUSTAINED: 600,
        TimeWindow.DAILY: 100000,
    },
    EndpointCategory.SPARQL_QUERY: {
        TimeWindow.BURST: 50,
        TimeWindow.SUSTAINED: 200,
        TimeWindow.DAILY: 50000,
    },
    EndpointCategory.GENERAL: {
        TimeWindow.BURST: 100,
        TimeWindow.SUSTAINED: 600,
        TimeWindow.DAILY: 100000,
    },
}


# Platform maximum rate limits (tenant config cannot exceed these)
# These are the absolute maximums that tenants can configure
PLATFORM_MAXIMUM_LIMITS: dict[str, dict[int, int]] = {
    # Authentication endpoints: Maximum 20 requests/minute
    EndpointCategory.AUTH: {
        TimeWindow.BURST: 10,  # Maximum 10 requests per 10 seconds
        TimeWindow.SUSTAINED: 20,  # Maximum 20 requests per minute
        TimeWindow.DAILY: 5000,  # Maximum 5,000 requests per day
    },
    # Asset management endpoints: Maximum 500 requests/minute
    EndpointCategory.ASSET: {
        TimeWindow.BURST: 100,  # Maximum 100 requests per 10 seconds
        TimeWindow.SUSTAINED: 500,  # Maximum 500 requests per minute
        TimeWindow.DAILY: 200000,  # Maximum 200,000 requests per day
    },
    # Contract management endpoints: Maximum 500 requests/minute
    EndpointCategory.CONTRACT: {
        TimeWindow.BURST: 100,  # Maximum 100 requests per 10 seconds
        TimeWindow.SUSTAINED: 500,  # Maximum 500 requests per minute
        TimeWindow.DAILY: 200000,  # Maximum 200,000 requests per day
    },
    # Search endpoints: Maximum 200 requests/minute
    EndpointCategory.SEARCH: {
        TimeWindow.BURST: 50,  # Maximum 50 requests per 10 seconds
        TimeWindow.SUSTAINED: 200,  # Maximum 200 requests per minute
        TimeWindow.DAILY: 100000,  # Maximum 100,000 requests per day
    },
    # File upload endpoints: Maximum 50 requests/minute
    EndpointCategory.FILE_UPLOAD: {
        TimeWindow.BURST: 15,  # Maximum 15 uploads per 10 seconds
        TimeWindow.SUSTAINED: 50,  # Maximum 50 uploads per minute
        TimeWindow.DAILY: 20000,  # Maximum 20,000 uploads per day
    },
    EndpointCategory.DQ_RUN: {
        TimeWindow.BURST: 100,
        TimeWindow.SUSTAINED: 300,
        TimeWindow.DAILY: 100000,
    },
    EndpointCategory.COMPLIANCE_RUN: {
        TimeWindow.BURST: 100,
        TimeWindow.SUSTAINED: 300,
        TimeWindow.DAILY: 100000,
    },
    EndpointCategory.FILE_DOWNLOAD: {
        TimeWindow.BURST: 500,
        TimeWindow.SUSTAINED: 3000,
        TimeWindow.DAILY: 500000,
    },
    EndpointCategory.CONTRACT_VALIDATION: {
        TimeWindow.BURST: 200,
        TimeWindow.SUSTAINED: 500,
        TimeWindow.DAILY: 200000,
    },
    EndpointCategory.CATALOG_READ: {
        TimeWindow.BURST: 1000,
        TimeWindow.SUSTAINED: 6000,
        TimeWindow.DAILY: 1000000,
    },
    EndpointCategory.SPARQL_QUERY: {
        TimeWindow.BURST: 500,
        TimeWindow.SUSTAINED: 2000,
        TimeWindow.DAILY: 500000,
    },
    EndpointCategory.GENERAL: {
        TimeWindow.BURST: 1000,
        TimeWindow.SUSTAINED: 6000,
        TimeWindow.DAILY: 1000000,
    },
}


def get_platform_default_limit(category: str, window: int) -> int:
    """
    Get platform default rate limit for category and window.

    Args:
        category: Endpoint category
        window: Time window in seconds

    Returns:
        Default limit
    """
    return PLATFORM_DEFAULT_LIMITS.get(category, {}).get(window, 100)


def get_platform_maximum_limit(category: str, window: int) -> int:
    """
    Get platform maximum rate limit for category and window.

    Args:
        category: Endpoint category
        window: Time window in seconds

    Returns:
        Maximum limit
    """
    return PLATFORM_MAXIMUM_LIMITS.get(category, {}).get(window, 1000)


def get_tenant_rate_limit(tenant_id: str, category: str, window: int) -> int:
    """
    Get rate limit for tenant, category, and window.

    Checks tenant config first, falls back to platform defaults.
    Ensures tenant limits don't exceed platform maximums.

    Args:
        tenant_id: Tenant UUID
        category: Endpoint category
        window: Time window in seconds

    Returns:
        Rate limit (tenant config or platform default, capped at platform maximum)
    """
    from django.core.exceptions import ValidationError as DjangoValidationError
    from django.db import IntegrityError

    from hub.apps.tenants.models import TenantConfig

    try:
        tenant_config, _created = TenantConfig.objects.get_or_create(
            tenant_id=tenant_id,
            defaults={"rate_limits": {}, "notification_opt_outs": {}},
        )
        rate_limits = tenant_config.rate_limits or {}

        # Get limit for category and window
        category_limits = rate_limits.get(category, {})
        limit = category_limits.get(str(window))

        if limit is not None:
            # Ensure limit doesn't exceed platform maximum
            max_limit = get_platform_maximum_limit(category, window)
            return min(limit, max_limit)
    except (TenantConfig.DoesNotExist, IntegrityError, DjangoValidationError):
        # tenant_id may reference a non-existent Tenant — the
        # get_or_create → full_clean path raises ValidationError when
        # the FK target is missing, and the DB raises IntegrityError.
        # Fall through to the platform default in either case.
        pass

    # Fall back to platform default; when E2E relax is on, use higher limits for
    # all common categories so 4+ parallel Playwright workers don't hit 429
    if getattr(settings, "RATE_LIMIT_E2E_RELAX", False):
        if category == EndpointCategory.AUTH:
            return 500 if window == 60 else (100 if window == 10 else 5000)
        if category == EndpointCategory.FILE_UPLOAD:
            return 100 if window == 60 else (30 if window == 10 else 10000)
        # Asset and contract reads/writes fire in parallel across multiple test workers;
        # 20-burst / 100-sustained is too tight for concurrent E2E batches.
        if category in (EndpointCategory.ASSET, EndpointCategory.CONTRACT):
            return 1000 if window == 60 else (200 if window == 10 else 100000)
    return get_platform_default_limit(category, window)


def get_user_rate_limit(tenant_id: str, category: str, window: int) -> int:
    """
    Get rate limit for user (50% of tenant limit).

    Args:
        tenant_id: Tenant UUID
        category: Endpoint category
        window: Time window in seconds

    Returns:
        User rate limit (50% of tenant limit, rounded down)
    """
    tenant_limit = get_tenant_rate_limit(tenant_id, category, window)
    return max(1, tenant_limit // 2)  # 50% of tenant limit, minimum 1


def get_api_key_rate_limit(tenant_id: str, category: str, window: int) -> int:
    """
    Get rate limit for API key (same as user limit).

    Args:
        tenant_id: Tenant UUID
        category: Endpoint category
        window: Time window in seconds

    Returns:
        API key rate limit (same as user limit)
    """
    return get_user_rate_limit(tenant_id, category, window)
