"""
Tenant Middleware

Enforces tenant suspension read-only behavior and tenant isolation.
"""
from django.http import HttpResponseForbidden, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from .models import Tenant, TenantStatus


class TenantSuspensionMiddleware(MiddlewareMixin):
    """
    Middleware to enforce read-only mode for suspended tenants.
    
    Blocks write operations (POST, PUT, PATCH, DELETE) for suspended tenants.
    Allows read operations (GET, HEAD, OPTIONS).
    """
    
    # HTTP methods that are considered write operations
    WRITE_METHODS = ["POST", "PUT", "PATCH", "DELETE"]
    
    # Endpoints that are always allowed (health checks, etc.)
    ALLOWED_PATHS = [
        "/health/",
        "/api/health/",
    ]
    
    def process_request(self, request):
        """Check if tenant is suspended and block writes"""
        # Skip if path is in allowed list
        if any(request.path.startswith(path) for path in self.ALLOWED_PATHS):
            return None
        
        # Get tenant from request (set by authentication middleware)
        tenant = getattr(request, "tenant", None)
        
        if not tenant:
            return None  # No tenant context, let other middleware handle
        
        # Check if tenant is suspended
        if tenant.status == TenantStatus.SUSPENDED:
            # Block write operations
            if request.method in self.WRITE_METHODS:
                return JsonResponse(
                    {"error": "Tenant is suspended. Write operations are not allowed."},
                    status=403
                )
        
        # Block all operations for deleted tenants
        elif tenant.status == TenantStatus.DELETED:
            return JsonResponse(
                {"error": "Tenant is deleted. All access is blocked."},
                status=403
            )
        
        return None

