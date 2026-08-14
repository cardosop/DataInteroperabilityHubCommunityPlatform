"""
Rate Limiting Service

Service layer for rate limit checking with multi-level enforcement.
"""

import structlog
from django.http import HttpRequest

from hub.apps.core.rate_limiting.config import get_api_key_rate_limit, get_tenant_rate_limit, get_user_rate_limit
from hub.apps.core.rate_limiting.utils import (
    EndpointCategory,
    TimeWindow,
    generate_rate_limit_key,
    get_endpoint_category,
    sliding_window_check,
)

logger = structlog.get_logger(__name__)


class RateLimitResult:
    """Result of rate limit check"""

    def __init__(
        self,
        allowed: bool,
        limit: int,
        remaining: int,
        reset_time: int,
        limit_type: str,
        category: str,
        window: int,
    ):
        self.allowed = allowed
        self.limit = limit
        self.remaining = remaining
        self.reset_time = reset_time
        self.limit_type = limit_type  # 'tenant', 'user', 'api_key'
        self.category = category
        self.window = window


def check_rate_limit(
    request: HttpRequest,
    tenant_id: str | None = None,
    user_id: str | None = None,
    api_key_id: str | None = None,
) -> tuple[bool, list[RateLimitResult]]:
    """
    Check rate limits for a request at all applicable levels.

    Checks tenant, user, and API-key limits (if applicable).
    All limits must pass for request to be allowed.

    Args:
        request: HTTP request object
        tenant_id: Tenant UUID (from request.tenant if not provided)
        user_id: User UUID (from request.user if not provided)
        api_key_id: API key UUID (from request.api_key_obj if not provided)

    Returns:
        Tuple of (is_allowed, list_of_results)
        - is_allowed: True if all limits pass, False if any limit exceeded
        - list_of_results: List of RateLimitResult for each limit checked
    """
    # Get identifiers from request if not provided
    if tenant_id is None:
        # Try request.tenant_id first (set by authentication/middleware)
        tenant_id = getattr(request, "tenant_id", None)
        if tenant_id:
            # Ensure it's a string
            tenant_id = str(tenant_id)
        else:
            # Fallback to request.tenant
            tenant = getattr(request, "tenant", None)
            tenant_id = str(tenant.id) if tenant and hasattr(tenant, "id") else None

    if user_id is None:
        user = getattr(request, "user", None)
        if user and hasattr(user, "is_authenticated") and user.is_authenticated:
            user_id = str(user.id)
        else:
            user_id = None

    # Single identity (feat1 D2): same request.api_key_obj used for BaaS quota/usage
    if api_key_id is None:
        api_key_obj = getattr(request, "api_key_obj", None)
        if api_key_obj:
            api_key_id = str(api_key_obj.id)
        else:
            api_key_id = None

    # Skip rate limiting if no tenant (shouldn't happen in normal flow)
    if not tenant_id:
        logger.warning("rate_limit_check_no_tenant", path=request.path)
        return True, []

    # Get endpoint category
    category = get_endpoint_category(request.path, request.method)

    # Check all applicable time windows
    windows = [TimeWindow.BURST, TimeWindow.SUSTAINED, TimeWindow.DAILY]
    results = []
    all_allowed = True

    # Check tenant limits
    for window in windows:
        limit = get_tenant_rate_limit(tenant_id, category, window)
        key = generate_rate_limit_key(
            tenant_id=tenant_id, endpoint_category=category, window=window
        )

        allowed, count, reset_time = sliding_window_check(key, limit, window)
        remaining = max(0, limit - count)

        result = RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            reset_time=reset_time,
            limit_type="tenant",
            category=category,
            window=window,
        )
        results.append(result)

        if not allowed:
            all_allowed = False
            logger.warning(
                "rate_limit_exceeded",
                tenant_id=tenant_id,
                category=category,
                window=window,
                limit_type="tenant",
                limit=limit,
                count=count,
            )
            # Don't check other windows if one is exceeded
            break

    # If tenant limit passed, check user limit (if user authenticated)
    if all_allowed and user_id:
        for window in windows:
            limit = get_user_rate_limit(tenant_id, category, window)
            key = generate_rate_limit_key(
                tenant_id=tenant_id, user_id=user_id, endpoint_category=category, window=window
            )

            allowed, count, reset_time = sliding_window_check(key, limit, window)
            remaining = max(0, limit - count)

            result = RateLimitResult(
                allowed=allowed,
                limit=limit,
                remaining=remaining,
                reset_time=reset_time,
                limit_type="user",
                category=category,
                window=window,
            )
            results.append(result)

            if not allowed:
                all_allowed = False
                logger.warning(
                    "rate_limit_exceeded",
                    tenant_id=tenant_id,
                    user_id=user_id,
                    category=category,
                    window=window,
                    limit_type="user",
                    limit=limit,
                    count=count,
                )
                break

    # If user limit passed, check API-key limit (if API key used)
    if all_allowed and api_key_id:
        for window in windows:
            limit = get_api_key_rate_limit(tenant_id, category, window)
            key = generate_rate_limit_key(
                tenant_id=tenant_id,
                api_key_id=api_key_id,
                endpoint_category=category,
                window=window,
            )

            allowed, count, reset_time = sliding_window_check(key, limit, window)
            remaining = max(0, limit - count)

            result = RateLimitResult(
                allowed=allowed,
                limit=limit,
                remaining=remaining,
                reset_time=reset_time,
                limit_type="api_key",
                category=category,
                window=window,
            )
            results.append(result)

            if not allowed:
                all_allowed = False
                logger.warning(
                    "rate_limit_exceeded",
                    tenant_id=tenant_id,
                    api_key_id=api_key_id,
                    category=category,
                    window=window,
                    limit_type="api_key",
                    limit=limit,
                    count=count,
                )
                break

    return all_allowed, results


def get_rate_limit_headers(request: HttpRequest, results: list[RateLimitResult]) -> dict[str, str]:
    """
    Generate rate limit headers for response.

    Adds standard rate limit headers:
    - X-RateLimit-Limit: Maximum number of requests allowed per window
    - X-RateLimit-Remaining: Number of requests remaining in current window
    - X-RateLimit-Reset: Unix timestamp when the rate limit window resets

    Uses the most restrictive limit (usually the one that was checked first).
    Prefers sustained window (most commonly used) if available.

    Args:
        request: HTTP request object
        results: List of RateLimitResult from check_rate_limit

    Returns:
        Dictionary of header name -> header value
    """
    if not results:
        return {}

    # Use the first result (usually tenant-level, most restrictive)
    # Prefer sustained window (most commonly used) if available
    sustained_result = next((r for r in results if r.window == TimeWindow.SUSTAINED), results[0])

    # Standard rate limit headers (RFC 6585, GitHub/GitLab style)
    headers = {
        "X-RateLimit-Limit": str(sustained_result.limit),
        "X-RateLimit-Remaining": str(max(0, sustained_result.remaining)),  # Ensure non-negative
        "X-RateLimit-Reset": str(sustained_result.reset_time),  # Unix timestamp
    }

    # Add category-specific headers if needed (for debugging/monitoring)
    if sustained_result.category != EndpointCategory.GENERAL:
        headers["X-RateLimit-Category"] = sustained_result.category

    # Add limit type header (tenant/user/api_key) for debugging
    headers["X-RateLimit-Type"] = sustained_result.limit_type

    return headers
