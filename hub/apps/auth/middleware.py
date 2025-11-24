"""
Authentication Middleware

Middleware for tenant scoping and request enrichment.
"""
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model

User = get_user_model()


class TenantScopingMiddleware(MiddlewareMixin):
    """
    Middleware to extract and set tenant_id from JWT token or API key.
    
    Sets request.tenant_id and request.tenant for use in views.
    """
    
    def process_request(self, request):
        """Extract tenant_id from token payload or API key"""
        # tenant_id is already set by authentication classes
        # This middleware can be used for additional tenant-related logic
        
        # If tenant_id is set by authentication, try to get tenant object
        if hasattr(request, 'tenant_id') and request.tenant_id:
            try:
                from hub.apps.tenants.models import Tenant
                request.tenant = Tenant.objects.get(id=request.tenant_id)
            except Tenant.DoesNotExist:
                request.tenant = None
        elif hasattr(request, 'user') and request.user.is_authenticated:
            # Fallback: get tenant from user
            if hasattr(request.user, 'tenant') and request.user.tenant:
                request.tenant_id = str(request.user.tenant.id)
                request.tenant = request.user.tenant
        
        return None

