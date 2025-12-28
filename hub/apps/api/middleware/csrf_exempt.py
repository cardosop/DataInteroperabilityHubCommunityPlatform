"""
CSRF Exemption Middleware for API Endpoints

This middleware exempts API endpoints from CSRF protection when using
API key or JWT token authentication, as these authentication methods
don't require CSRF protection.
"""
from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.csrf import csrf_exempt


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
        if request.path.startswith('/api/v1/'):
            # Check if request has API key or Bearer token authentication
            auth_header = request.headers.get('Authorization', '')
            has_api_key_header = request.headers.get('X-API-Key') is not None
            has_bearer_token = auth_header.startswith('Bearer ')
            has_api_key_auth = auth_header.startswith('ApiKey ')

            # Exempt if using API key (via X-API-Key header or Authorization: ApiKey) or Bearer token
            if has_api_key_header or has_bearer_token or has_api_key_auth:
                # Mark the view as CSRF exempt
                # This is done by setting an attribute that CSRF middleware checks
                setattr(request, '_dont_enforce_csrf_checks', True)

        return None

