"""
CSRF Exemption Middleware for API Endpoints

This middleware exempts API endpoints from CSRF protection when using
API key or JWT token authentication, as these authentication methods
don't require CSRF protection.
"""

from django.utils.deprecation import MiddlewareMixin


class APIEndpointCSRFExemptMiddleware(MiddlewareMixin):
    """
    Middleware to exempt API endpoints from CSRF protection.

    API endpoints using API key or JWT token authentication don't need
    CSRF protection since they use stateless authentication.
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Exempt API endpoints from CSRF protection.

        This runs before CSRF middleware checks the request.
        """
        # Exempt all /api/v1/ endpoints from CSRF
        if request.path.startswith("/api/v1/"):
            # All API endpoints use stateless authentication (JWT, ApiKey)
            # or DRF's force_authenticate — none need CSRF protection.
            request._dont_enforce_csrf_checks = True
