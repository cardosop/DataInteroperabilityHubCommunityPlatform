"""
API Gateway Middleware

Middleware for request routing, authentication, rate limiting, logging, and tracing.
"""
import os
import sys
import time
from typing import Callable, Optional, Tuple
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from asgiref.sync import sync_to_async
import httpx
import structlog

from rate_limiter import RateLimiter
from api_key_manager import APIKeyManager, APIKeyInfo
from routing import get_backend_url

# Django is already set up in main.py, so we can import directly
# Import UsageTrackingService for usage tracking
try:
    from hub.apps.baas.services import UsageTrackingService
except ImportError:
    # Django not set up yet (e.g., during testing), will be set up by main.py
    UsageTrackingService = None

logger = structlog.get_logger(__name__)


class APIGatewayMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API Gateway functionality.

    Handles:
    - API key authentication
    - Rate limiting (per-tier, per-tenant, per-user)
    - Request routing to backend services
    - Request/response logging
    - Error handling and transformation
    """

    def __init__(
        self,
        app,
        rate_limiter: RateLimiter,
        api_key_manager: APIKeyManager
    ):
        """
        Initialize API Gateway middleware.

        Args:
            app: ASGI application (required by BaseHTTPMiddleware)
            rate_limiter: Rate limiter instance
            api_key_manager: API key manager instance
        """
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.api_key_manager = api_key_manager
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through API Gateway middleware.

        Args:
            request: FastAPI request
            call_next: Next middleware/endpoint handler

        Returns:
            Response from backend service or error response
        """
        start_time = time.time()
        request_id = f"{int(time.time() * 1000000)}"

        # Skip middleware for health, metrics, and root endpoints
        if request.url.path in ['/health', '/metrics', '/', '/api/v1/health']:
            return await call_next(request)

        # Extract API key from request
        api_key = self._extract_api_key(request)
        api_key_info: Optional[APIKeyInfo] = None

        # Validate API key (use sync_to_async for Django ORM calls from async context)
        if api_key:
            # Wrap the method call properly for sync_to_async
            validate_key = sync_to_async(self.api_key_manager.validate_api_key)
            api_key_info = await validate_key(api_key)
            if api_key_info is None:
                logger.warning(
                    "api_key_validation_failed",
                    request_id=request_id,
                    path=request.url.path,
                    method=request.method
                )
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error": "Invalid or expired API key",
                        "request_id": request_id
                    }
                )
        else:
            # API key is required for all requests except health/metrics
            logger.warning(
                "api_key_missing",
                request_id=request_id,
                path=request.url.path,
                method=request.method
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "API key required",
                    "request_id": request_id
                }
            )

        # Check rate limits
        rate_limit_passed, rate_limit_info = await self._check_rate_limits(
            api_key_info,
            request_id
        )

        if not rate_limit_passed:
            logger.warning(
                "rate_limit_exceeded",
                request_id=request_id,
                api_key_id=api_key_info.api_key_id,
                tenant_id=api_key_info.tenant_id,
                tier=api_key_info.tier
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "request_id": request_id,
                    "retry_after": rate_limit_info.get('retry_after', 3600)
                },
                headers={
                    "X-RateLimit-Limit": str(rate_limit_info.get('limit', 0)),
                    "X-RateLimit-Remaining": str(rate_limit_info.get('remaining', 0)),
                    "X-RateLimit-Reset": str(rate_limit_info.get('reset_time', 0)),
                    "Retry-After": str(rate_limit_info.get('retry_after', 3600))
                }
            )

        # Route request to backend service using routing configuration
        backend_service_url = get_backend_url(request.url.path)

        if backend_service_url is None:
            logger.warning(
                "route_not_found",
                request_id=request_id,
                path=request.url.path,
                method=request.method
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": "Route not found",
                    "request_id": request_id,
                    "path": request.url.path
                }
            )

        try:
            # Build backend URL with path and query string
            backend_url = f"{backend_service_url.rstrip('/')}{request.url.path}"
            if request.url.query:
                backend_url += f"?{request.url.query}"

            # Prepare request headers (forward original headers, add gateway headers)
            headers = dict(request.headers)
            headers.pop('host', None)  # Remove host header
            headers['X-Gateway-Request-ID'] = request_id
            headers['X-Gateway-Tenant-ID'] = api_key_info.tenant_id
            if api_key_info.user_id:
                headers['X-Gateway-User-ID'] = api_key_info.user_id

            # Forward request to backend
            method = request.method
            body = await request.body() if method in ['POST', 'PUT', 'PATCH'] else None

            # Calculate request size
            request_size_bytes = len(body) if body else 0
            if 'content-length' in request.headers:
                try:
                    request_size_bytes = int(request.headers['content-length'])
                except (ValueError, TypeError):
                    pass

            backend_response = await self.http_client.request(
                method=method,
                url=backend_url,
                headers=headers,
                content=body,
                follow_redirects=True
            )

            # Calculate response size
            response_size_bytes = len(backend_response.content) if backend_response.content else 0
            if 'content-length' in backend_response.headers:
                try:
                    response_size_bytes = int(backend_response.headers['content-length'])
                except (ValueError, TypeError):
                    pass

            # Create response with rate limit headers
            response_headers = dict(backend_response.headers)
            response_headers.update({
                "X-RateLimit-Limit": str(rate_limit_info.get('limit', 0)),
                "X-RateLimit-Remaining": str(rate_limit_info.get('remaining', 0)),
                "X-RateLimit-Reset": str(rate_limit_info.get('reset_time', 0)),
                "X-Gateway-Request-ID": request_id
            })

            response = Response(
                content=backend_response.content,
                status_code=backend_response.status_code,
                headers=response_headers,
                media_type=backend_response.headers.get('content-type', 'application/json')
            )

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log request/response with route information
            logger.info(
                "api_gateway_request",
                request_id=request_id,
                method=method,
                path=request.url.path,
                backend_service=backend_service_url,
                status_code=backend_response.status_code,
                duration_ms=round(duration_ms, 2),
                api_key_id=api_key_info.api_key_id,
                tenant_id=api_key_info.tenant_id,
                tier=api_key_info.tier
            )

            # Track usage (non-blocking, don't fail request if tracking fails)
            if UsageTrackingService is not None:
                try:
                    usage_tracker = UsageTrackingService(
                        tenant_id=api_key_info.tenant_id,
                        user_id=api_key_info.user_id
                    )
                    track_request = sync_to_async(usage_tracker.track_request)
                    await track_request(
                        api_key_id=api_key_info.api_key_id,
                        endpoint=request.url.path,
                        method=method,
                        status_code=backend_response.status_code,
                        response_time_ms=duration_ms,
                        request_size_bytes=request_size_bytes,
                        response_size_bytes=response_size_bytes
                    )
                except Exception as e:
                    # Log but don't fail the request if usage tracking fails
                    logger.warning(
                        "usage_tracking_failed",
                        request_id=request_id,
                        error=str(e),
                        api_key_id=api_key_info.api_key_id
                    )

            return response

        except httpx.TimeoutException:
            logger.error(
                "backend_timeout",
                request_id=request_id,
                path=request.url.path,
                method=request.method
            )
            return JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content={
                    "error": "Backend service timeout",
                    "request_id": request_id
                }
            )
        except httpx.RequestError as e:
            logger.error(
                "backend_error",
                request_id=request_id,
                path=request.url.path,
                method=request.method,
                error=str(e)
            )
            return JSONResponse(
                status_code=status.HTTP_502_BAD_GATEWAY,
                content={
                    "error": "Backend service error",
                    "request_id": request_id
                }
            )
        except Exception as e:
            logger.error(
                "gateway_error",
                request_id=request_id,
                path=request.url.path,
                method=request.method,
                error=str(e)
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal gateway error",
                    "request_id": request_id
                }
            )

    def _extract_api_key(self, request: Request) -> Optional[str]:
        """
        Extract API key from request headers.

        Checks:
        1. Authorization header: "ApiKey <key>"
        2. X-API-Key header

        Args:
            request: FastAPI request

        Returns:
            API key string or None
        """
        # Check Authorization header
        auth_header = request.headers.get('authorization', '')
        if auth_header.startswith('ApiKey '):
            return auth_header.split(' ', 1)[1] if ' ' in auth_header else None

        # Check X-API-Key header
        return request.headers.get('x-api-key')

    async def _check_rate_limits(
        self,
        api_key_info: APIKeyInfo,
        request_id: str
    ) -> Tuple[bool, dict]:
        """
        Check all applicable rate limits.

        Checks in order:
        1. Tier limit
        2. Tenant limit (if configured)
        3. API key limit (if configured)

        Args:
            api_key_info: API key information
            request_id: Request ID for logging

        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        tier = api_key_info.tier

        # Check tier limit
        tier_allowed, tier_count, tier_reset = await sync_to_async(
            lambda: self.rate_limiter.check_tier_limit(tier)
        )()
        if not tier_allowed:
            logger.warning(
                "rate_limit_tier_exceeded",
                request_id=request_id,
                tenant_id=api_key_info.tenant_id,
                tier=tier
            )
            return False, {
                'limit': self._get_tier_limit(tier),
                'remaining': 0,
                'reset_time': tier_reset,
                'retry_after': max(1, tier_reset - int(time.time()))
            }

        # Check tenant limit (from TenantConfig.rate_limits["api_gateway_requests_per_hour"])
        tenant_limit = await sync_to_async(
            self.api_key_manager.get_tenant_rate_limit
        )(api_key_info.tenant_id)
        if tenant_limit is not None:
            tenant_allowed, tenant_count, tenant_reset = await sync_to_async(
                lambda: self.rate_limiter.check_tenant_limit(
                    api_key_info.tenant_id, limit=tenant_limit
                )
            )()
            if not tenant_allowed:
                logger.warning(
                    "rate_limit_tenant_exceeded",
                    request_id=request_id,
                    tenant_id=api_key_info.tenant_id,
                    limit=tenant_limit
                )
                return False, {
                    'limit': tenant_limit,
                    'remaining': 0,
                    'reset_time': tenant_reset,
                    'retry_after': max(1, tenant_reset - int(time.time()))
                }

        # Check API key limit (from APIKey.rate_limit_per_hour)
        api_key_limit = getattr(api_key_info, 'rate_limit_per_hour', None)
        if api_key_limit is not None:
            api_key_allowed, api_key_count, api_key_reset = await sync_to_async(
                lambda: self.rate_limiter.check_api_key_limit(
                    api_key_info.api_key_id, limit=api_key_limit
                )
            )()
            if not api_key_allowed:
                logger.warning(
                    "rate_limit_apikey_exceeded",
                    request_id=request_id,
                    api_key_id=api_key_info.api_key_id,
                    limit=api_key_limit
                )
                return False, {
                    'limit': api_key_limit,
                    'remaining': 0,
                    'reset_time': api_key_reset,
                    'retry_after': max(1, api_key_reset - int(time.time()))
                }

        # All limits passed; use tier for response headers
        tier_limit = self._get_tier_limit(tier)
        return True, {
            'limit': tier_limit,
            'remaining': max(0, tier_limit - tier_count - 1) if tier_limit else None,
            'reset_time': tier_reset,
            'retry_after': max(1, tier_reset - int(time.time()))
        }

    def _get_tier_limit(self, tier: str) -> Optional[int]:
        """Get rate limit for a tier."""
        from rate_limiter import RateLimitTier
        tier_upper = tier.upper()
        if tier_upper == 'FREE':
            return RateLimitTier.FREE
        elif tier_upper == 'PRO':
            return RateLimitTier.PRO
        elif tier_upper == 'ENTERPRISE':
            return RateLimitTier.ENTERPRISE
        else:
            return RateLimitTier.FREE
