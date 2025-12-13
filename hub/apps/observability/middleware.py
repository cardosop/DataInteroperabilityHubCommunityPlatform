"""
Observability: Metrics Middleware

Middleware to track HTTP request metrics using OpenTelemetry.

This middleware automatically records:
- HTTP request counts (http_requests_total)
- HTTP request durations (http_request_duration_seconds)
- HTTP errors (http_errors_total)

All metrics are exported via the OpenTelemetry Prometheus exporter and available
at the `/metrics` endpoint in Prometheus format.
"""
import re
import time

from .otel_metrics import (
    get_status_class,
    http_errors_total,
    http_request_duration_seconds,
    http_requests_total,
)


class MetricsMiddleware:
    """
    Middleware to track HTTP request metrics using OpenTelemetry.
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
    """
    Middleware to track HTTP request metrics for Prometheus.
    """

    def process_request(self, request):
        """Record request start time"""
        request._metrics_start_time = time.time()

    def process_response(self, request, response):
        """Record request metrics"""
        if not hasattr(request, '_metrics_start_time'):
            return response

        # Calculate duration
        duration = time.time() - request._metrics_start_time

        # Get route (simplified - use path without query params)
        route = request.path
        # Normalize route (remove IDs for better aggregation)
        route = self._normalize_route(route)

        # Get method and status
        method = request.method
        status_code = response.status_code
        status_class = get_status_class(status_code)

        # Record metrics
        http_requests_total.labels(
            method=method,
            route=route,
            status_class=status_class
        ).inc()

        http_request_duration_seconds.labels(
            method=method,
            route=route,
            status_class=status_class
        ).observe(duration)

        # Record errors
        if status_code >= 400:
            http_errors_total.labels(
                method=method,
                route=route,
                status_code=status_code
            ).inc()

        return response

    def _normalize_route(self, route: str) -> str:
        """
        Normalize route by replacing UUIDs and IDs with placeholders.

        Args:
            route: Request path

        Returns:
            Normalized route
        """
        # Replace UUIDs with {id}
        route = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', route, flags=re.IGNORECASE)
        # Replace numeric IDs with {id}
        route = re.sub(r'/\d+', '/{id}', route)
        return route

