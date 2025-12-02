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
        
        # Get tenant_id to fetch fresh tenant from database
        # We always fetch from DB to avoid cached objects with stale status
        tenant_id = None
        
        # Try multiple sources for tenant_id, in order of preference
        # 1. Check request.tenant_id (set by authentication or TenantScopingMiddleware)
        if hasattr(request, "tenant_id") and request.tenant_id:
            tenant_id = request.tenant_id
        
        # 2. Check request.tenant (set by TenantScopingMiddleware)
        if tenant_id is None and hasattr(request, "tenant") and request.tenant:
            tenant_id = request.tenant.id
            # Set request.tenant_id for consistency
            if tenant_id:
                request.tenant_id = tenant_id
        
        # 3. Check request.user and query from database
        # This is the most reliable source in test environments
        if tenant_id is None and hasattr(request, "user") and request.user:
            # Check if user is authenticated (works with both force_authenticate and JWT)
            from django.contrib.auth.models import AnonymousUser
            is_anonymous = isinstance(request.user, AnonymousUser)
            
            # User is considered authenticated if not AnonymousUser and has an id
            if not is_anonymous and hasattr(request.user, "id") and request.user.id is not None:
                # Get tenant_id by querying user from database to avoid cached relationship issues
                # This ensures we get the actual tenant_id from the database, not from a cached object
                try:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    # Query user from database to get fresh tenant_id
                    db_user = User.objects.only("tenant_id").get(id=request.user.id)
                    tenant_id = db_user.tenant_id
                    # Set request.tenant_id and request.tenant for consistency
                    if tenant_id:
                        request.tenant_id = tenant_id
                        # Also set request.tenant if not already set
                        if not hasattr(request, "tenant") or not request.tenant:
                            try:
                                request.tenant = Tenant.objects.get(id=tenant_id)
                            except Tenant.DoesNotExist:
                                pass
                except (User.DoesNotExist, AttributeError, Exception):
                    # Fallback: try to get from the user object directly
                    tenant_id = getattr(request.user, "tenant_id", None)
                    if tenant_id is None and hasattr(request.user, "tenant") and request.user.tenant:
                        tenant_id = request.user.tenant.id
                        # Set request.tenant_id for consistency
                        if tenant_id:
                            request.tenant_id = tenant_id
        
        # 3. Last resort: try to get it from request.tenant
        if tenant_id is None:
            tenant = getattr(request, "tenant", None)
            if tenant:
                tenant_id = tenant.id
        
        # Always fetch tenant directly from database to get latest status
        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                # Update request.tenant with fresh object
                request.tenant = tenant
            except Tenant.DoesNotExist:
                return None  # No tenant found, let other middleware handle
        else:
            return None  # No tenant context, let other middleware handle
        
        # Check if tenant is suspended (we already have fresh object from DB)
        # Double-check status by refreshing from DB (defensive programming)
        tenant.refresh_from_db()
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

