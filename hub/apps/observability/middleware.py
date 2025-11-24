"""
Observability: Metrics Middleware

Middleware to track HTTP request metrics.
"""
import time
from django.utils.deprecation import MiddlewareMixin
from .metrics import (
    http_requests_total,
    http_request_duration_seconds,
    http_errors_total,
    get_status_class,
)


class MetricsMiddleware(MiddlewareMixin):
    """
    Middleware to track HTTP request metrics for Prometheus.
    """
    
    def process_request(self, request):
        """Record request start time"""
        request._metrics_start_time = time.time()
        return None
    
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
        import re
        # Replace UUIDs with {id}
        route = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', route, flags=re.IGNORECASE)
        # Replace numeric IDs with {id}
        route = re.sub(r'/\d+', '/{id}', route)
        return route

