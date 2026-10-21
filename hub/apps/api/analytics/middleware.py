"""
API Analytics Middleware

Middleware for tracking API usage metrics.
"""

import time

import structlog
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from .analytics import APIAnalyticsService

logger = structlog.get_logger(__name__)


class APIAnalyticsMiddleware(MiddlewareMixin):
    """
    Middleware for tracking API usage metrics.
    """

    def process_request(self, request: HttpRequest):
        """Track request start time"""
        # Only track API requests
        if not request.path.startswith("/api/"):
            return None

        # Store start time for latency calculation
        request._api_analytics_start_time = time.time()

        # Track request size
        request._api_analytics_request_size = len(request.body) if hasattr(request, "body") else 0

        return None

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Track request metrics"""
        # Only track API requests
        if not request.path.startswith("/api/"):
            return response

        # Get tenant and user
        tenant_id = None
        user_id = None

        if hasattr(request, "tenant_id") and request.tenant_id:
            tenant_id = str(request.tenant_id)
        elif hasattr(request, "tenant") and request.tenant:
            tenant_id = str(request.tenant.id)

        if hasattr(request, "user") and request.user.is_authenticated:
            user_id = str(request.user.id)

        if not tenant_id:
            return response  # Skip if no tenant

        # Calculate latency
        latency_ms = None
        if hasattr(request, "_api_analytics_start_time"):
            latency_ms = (time.time() - request._api_analytics_start_time) * 1000

        # Get API version
        api_version = "v1"
        if hasattr(request, "api_version"):
            api_version = str(request.api_version)

        # Track request (async in production via background job)
        try:
            APIAnalyticsService.track_request(
                tenant_id=tenant_id,
                endpoint_path=request.path,
                method=request.method,
                status_code=response.status_code,
                latency_ms=latency_ms,
                user_id=user_id,
                request_size_bytes=getattr(request, "_api_analytics_request_size", None),
                response_size_bytes=len(response.content) if hasattr(response, "content") else None,
                api_version=api_version,
            )
        except Exception as e:
            logger.warning("api_analytics_tracking_error", error=str(e), endpoint_path=request.path)

        return response
