"""
API Middleware

Middleware for request ID generation, rate limiting, and request validation.
"""

import logging
import time
import uuid

import structlog
from django.core.cache import cache
from rest_framework.response import Response
from django.utils import timezone

logger = structlog.get_logger(__name__)


class RequestIDMiddleware:
    """
    Middleware to generate and attach request ID to each request.
    """

    def __init__(self, get_response):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response

    def __call__(self, request):
        """Process request and return response."""
        # Process request
        self.process_request(request)

        # Get response
        response = self.get_response(request)

        # Process response
        response = self.process_response(request, response)

        return response

    def process_request(self, request):
        """Capture or generate the request correlation identifier.

        Honors `X-Request-ID` (canonical, used by API clients) and
        `X-Correlation-ID` (frontend tracing convention — both names are
        listed as equivalent in CORS_ALLOW_HEADERS at settings.py:1537-1538).
        Precedence: `X-Request-ID` wins if both are present so existing
        callers' contracts are unchanged. The frontend's E2E correlation
        guard sends `X-Correlation-ID`; without this fall-through it would
        observe every API response as missing the echo it expects.
        """
        request_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Correlation-ID")
            or str(uuid.uuid4())
        )
        request.id = request_id
        request.request_id = request_id

        # Add request_id to structlog context
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            route=request.path,
            method=request.method,
        )

        # Add tenant_id and user_id if available (will be set later by auth middleware)
        return None

    def process_response(self, request, response):
        """Echo the request ID under both header names.

        `X-Request-ID` is the canonical platform header. `X-Correlation-ID`
        is added so the frontend's tracing/E2E-guard convention has a single
        round-trip pair: anything the caller sends under either name comes
        back under both names. The two values are identical because
        `process_request` resolves them to the same `request.request_id`.
        """
        if hasattr(request, "request_id"):
            response["X-Request-ID"] = request.request_id
            response["X-Correlation-ID"] = request.request_id

        # Add tenant_id and user_id to context if available
        if hasattr(request, "tenant") and request.tenant:
            structlog.contextvars.bind_contextvars(tenant_id=str(request.tenant.id))

        if hasattr(request, "user") and request.user.is_authenticated:
            structlog.contextvars.bind_contextvars(user_id=str(request.user.id))

        return response


class StructlogContextMiddleware:
    """
    Middleware that binds ``tenant_id`` and ``user_id`` into the structlog
    contextvars **before** the view runs (13.5).

    Why this is necessary
    ---------------------
    ``RequestIDMiddleware.process_response()`` adds these fields *after* the
    response has been built, so every log line emitted inside a view or
    service layer was missing ``tenant_id`` / ``user_id``.  Placing this
    middleware *after* ``TenantScopingMiddleware`` and Django's
    ``AuthenticationMiddleware`` in the MIDDLEWARE list guarantees that
    ``request.tenant`` and ``request.user`` are already populated when its
    ``__call__`` runs, so we can bind them before delegating to the next
    middleware / view.

    Cleanup
    -------
    ``django_structlog.middlewares.request.RequestMiddleware`` (position 4 in
    the stack) connects to Django's ``request_started`` signal and calls
    ``structlog.contextvars.clear_contextvars()`` at the very start of every
    new request, preventing cross-request context leakage.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ctx: dict = {}
        tenant = getattr(request, "tenant", None)
        if tenant is not None and hasattr(tenant, "id"):
            ctx["tenant_id"] = str(tenant.id)
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            ctx["user_id"] = str(user.id)
        if ctx:
            structlog.contextvars.bind_contextvars(**ctx)
        return self.get_response(request)


class SecurityHeadersMiddleware:
    """
    Middleware to add security headers (Django 6 enhancements).

    Adds additional security headers beyond Django's built-in SecurityMiddleware:
    - X-Content-Type-Options (if not already set)
    - Referrer-Policy
    - Permissions-Policy (optional)
    """

    def __init__(self, get_response):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response

    def __call__(self, request):
        """Process request and return response."""
        response = self.get_response(request)
        return self.process_response(request, response)

    def process_response(self, request, response):
        """Add security headers to response."""
        from django.conf import settings

        # X-Content-Type-Options (if not already set by SecurityMiddleware)
        if "X-Content-Type-Options" not in response:
            if getattr(settings, "SECURE_CONTENT_TYPE_NOSNIFF", True):
                response["X-Content-Type-Options"] = "nosniff"

        # Referrer-Policy
        referrer_policy = getattr(
            settings, "SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin"
        )
        if referrer_policy:
            response["Referrer-Policy"] = referrer_policy

        # Permissions-Policy (optional, configure as needed)
        permissions_policy = getattr(settings, "SECURE_PERMISSIONS_POLICY", None)
        if permissions_policy:
            # Convert dict to header format: "geolocation=(), camera=()"
            policy_parts = [f"{key}={value}" for key, value in permissions_policy.items()]
            response["Permissions-Policy"] = ", ".join(policy_parts)

        return response


class RateLimitMiddleware:
    """
    DEPRECATED: This middleware is deprecated. Use hub.apps.rate_limiting.middleware.RateLimitMiddleware instead.

    This middleware is kept for backward compatibility but should not be used in new code.
    It is not included in MIDDLEWARE settings and will be removed in a future version.

    Middleware for rate limiting per tenant, per user, and per endpoint.
    """

    def __init__(self, get_response):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response

    def __call__(self, request):
        """Process request and return response."""
        # Process request (may return early response)
        response = self.process_request(request)
        if response is not None:
            return response

        # Get response
        response = self.get_response(request)

        # Process response
        response = self.process_response(request, response)

        return response

    def process_request(self, request):
        """Check rate limits before processing request"""
        # Skip rate limiting for health checks and admin
        if request.path.startswith("/health/") or request.path.startswith("/admin/"):
            return None

        # Skip rate limiting for non-API endpoints
        if not request.path.startswith("/api/v1/"):
            return None

        # Get tenant and user from request
        tenant = getattr(request, "tenant", None)
        tenant_id = (
            str(tenant.id)
            if tenant and hasattr(tenant, "id")
            else (str(tenant) if tenant else None)
        )
        user_id = (
            getattr(request.user, "id", None)
            if hasattr(request, "user") and request.user.is_authenticated
            else None
        )

        # Rate limit key components
        endpoint = request.path
        method = request.method

        # Build rate limit keys
        keys = []
        if tenant_id:
            keys.append(f"rate_limit:tenant:{tenant_id}:{method}:{endpoint}")
        if user_id:
            keys.append(f"rate_limit:user:{user_id}:{method}:{endpoint}")

        # Check rate limits
        for key in keys:
            if not self._check_rate_limit(key, request):
                return Response(
                    {
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Rate limit exceeded for this endpoint",
                            "http_status": 429,
                            "request_id": getattr(request, "id", str(uuid.uuid4())),
                            "timestamp": timezone.now().isoformat(),
                            "details": {
                                "limit_type": "tenant" if "tenant" in key else "user",
                                "retry_after": 60,
                            },
                        }
                    },
                    status=429,
                )

        return None

    def _check_rate_limit(self, key, request):
        """
        Check if rate limit is exceeded.

        Args:
            key: Rate limit cache key
            request: HTTP request object

        Returns:
            True if within limit, False if exceeded
        """
        # Get rate limit configuration from settings
        from django.conf import settings

        limit = (
            getattr(settings, "RATE_LIMIT_PER_TENANT", 100)
            if "tenant" in key
            else getattr(settings, "RATE_LIMIT_PER_USER", 100)
        )
        window = getattr(settings, "RATE_LIMIT_WINDOW", 60)

        # Check if rate limiting is enabled
        if not getattr(settings, "RATE_LIMIT_ENABLED", True):
            return True

        # Get current count
        count = cache.get(key, 0)

        if count >= limit:
            # Rate limit exceeded
            ttl = cache.ttl(key)
            if ttl is None:
                ttl = window

            # Add retry-after header
            request.retry_after = ttl
            return False

        # Increment counter
        cache.set(key, count + 1, window)
        return True

    def process_response(self, request, response):
        """Add rate limit headers to response"""
        if hasattr(request, "retry_after"):
            response["Retry-After"] = str(request.retry_after)

        # Add rate limit headers
        if request.path.startswith("/api/v1/"):
            from django.conf import settings

            tenant_id = getattr(request, "tenant", None)
            if tenant_id:
                tenant_id = str(tenant_id.id) if hasattr(tenant_id, "id") else str(tenant_id)

            user_id = (
                getattr(request.user, "id", None)
                if hasattr(request, "user") and request.user.is_authenticated
                else None
            )

            # Always add tenant-level rate limit headers (use default if no tenant)
            limit = getattr(settings, "RATE_LIMIT_PER_TENANT", 100)
            if tenant_id:
                key = f"rate_limit:tenant:{tenant_id}:{request.method}:{request.path}"
                count = cache.get(key, 0)
            else:
                # Default limit when no tenant (for unauthenticated or system requests)
                count = 0
            response["X-RateLimit-Limit"] = str(limit)
            response["X-RateLimit-Remaining"] = str(max(0, limit - count))

            # Add user-level rate limit headers if user is authenticated
            if user_id:
                key = f"rate_limit:user:{user_id}:{request.method}:{request.path}"
                count = cache.get(key, 0)
                limit = getattr(settings, "RATE_LIMIT_PER_USER", 100)
                response["X-RateLimit-User-Limit"] = str(limit)
                response["X-RateLimit-User-Remaining"] = str(max(0, limit - count))

        return response
