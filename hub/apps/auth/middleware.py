"""
Authentication Middleware

Middleware for tenant scoping and request enrichment.

CRITICAL: This middleware runs BEFORE REST Framework authentication.
It extracts tenant_id from Authorization headers (API keys or JWT tokens)
so that rate limiting middleware can access it.

REST Framework authentication will run later and can override/validate.
"""
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
import structlog

logger = structlog.get_logger(__name__)

User = get_user_model()


class TenantScopingMiddleware(MiddlewareMixin):
    """
    Middleware to extract and set tenant_id from JWT token or API key.
    
    This runs BEFORE REST Framework authentication, so it extracts tenant_id
    directly from Authorization headers to support rate limiting middleware.
    
    Sets request.tenant_id and request.tenant for use in views and rate limiting.
    """
    
    def _extract_tenant_id_from_api_key(self, request):
        """
        Extract tenant_id from API key in Authorization header.
        
        This is a lightweight lookup that doesn't perform full authentication
        (no expiration checks, no last_used updates). Full authentication
        will happen later in REST Framework authentication classes.
        
        Returns tenant_id (UUID string) or None.
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        api_key = None
        
        if auth_header.startswith('ApiKey '):
            api_key = auth_header.split(' ', 1)[1] if ' ' in auth_header else None
        else:
            # Check X-API-Key header
            api_key = request.META.get('HTTP_X_API_KEY')
        
        if not api_key:
            return None
        
        try:
            from hub.apps.auth.models import APIKey
            # Hash the provided key
            key_hash = APIKey.hash_key(api_key)
            # Look up API key (lightweight - no expiration check here)
            # Full validation happens in REST Framework authentication
            api_key_obj = APIKey.objects.select_related('tenant').only('tenant_id', 'tenant').get(key_hash=key_hash)
            return str(api_key_obj.tenant.id)
        except APIKey.DoesNotExist:
            # Invalid API key - will be caught by REST Framework authentication
            return None
        except Exception as e:
            # Log but don't fail - let REST Framework authentication handle errors
            logger.debug("failed_to_extract_tenant_from_api_key", error=str(e))
            return None
    
    def _extract_tenant_id_from_jwt(self, request):
        """
        Extract tenant_id from JWT token in Authorization header.
        
        This is a lightweight decode that doesn't perform full validation
        (no user lookup, no token version check). Full validation
        will happen later in REST Framework authentication classes.
        
        Returns tenant_id (UUID string) or None.
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ', 1)[1] if ' ' in auth_header else None
        if not token:
            return None
        
        try:
            from hub.apps.auth.jwt_utils import JWTTokenGenerator
            # Decode token without full validation (just get payload)
            # Full validation happens in REST Framework authentication
            payload = JWTTokenGenerator.decode_access_token(token)
            if payload and 'tenant_id' in payload:
                return payload.get('tenant_id')
        except Exception as e:
            # Log but don't fail - let REST Framework authentication handle errors
            logger.debug("failed_to_extract_tenant_from_jwt", error=str(e))
            return None
        
        return None
    
    def process_request(self, request):
        """
        Extract tenant_id from Authorization header or request.user.
        
        Priority:
        1. If tenant_id already set, use it
        2. Extract from API key in Authorization header (for rate limiting)
        3. Extract from JWT token in Authorization header (for rate limiting)
        4. Get from request.user (set by Django's AuthenticationMiddleware)
        
        This ensures tenant_id is available for rate limiting middleware
        even though REST Framework authentication hasn't run yet.
        """
        # If tenant_id is already set, ensure it's a string and get tenant object
        if hasattr(request, 'tenant_id') and request.tenant_id:
            # Ensure tenant_id is a string (authentication might set it as UUID)
            if not isinstance(request.tenant_id, str):
                request.tenant_id = str(request.tenant_id)
            try:
                from hub.apps.tenants.models import Tenant
                # Fetch tenant object fresh from database (important for thread safety)
                if not hasattr(request, 'tenant') or not request.tenant:
                    request.tenant = Tenant.objects.get(id=request.tenant_id)
            except Exception:
                request.tenant = None
            return None
        
        # Try to extract tenant_id from Authorization header (for rate limiting)
        # This runs BEFORE REST Framework authentication
        tenant_id = None
        
        # Try API key first
        tenant_id = self._extract_tenant_id_from_api_key(request)
        
        # If not found, try JWT token
        if not tenant_id:
            tenant_id = self._extract_tenant_id_from_jwt(request)
        
        # If found from header, set it
        if tenant_id:
            request.tenant_id = str(tenant_id)
            try:
                from hub.apps.tenants.models import Tenant
                request.tenant = Tenant.objects.get(id=tenant_id)
            except Exception:
                request.tenant = None
            return None
        
        # Fallback: get tenant from request.user (set by Django's AuthenticationMiddleware)
        # This is for session-based authentication
        if hasattr(request, 'user') and request.user.is_authenticated:
            from django.contrib.auth.models import AnonymousUser
            if not isinstance(request.user, AnonymousUser) and hasattr(request.user, 'id') and request.user.id:
                try:
                    # Query user from database to get fresh tenant_id (avoid cached relationships)
                    # This is important for thread safety with LiveServerTestCase
                    db_user = User.objects.only('tenant_id').get(id=request.user.id)
                    if db_user.tenant_id:
                        request.tenant_id = str(db_user.tenant_id)
                        # Also set tenant object if not already set
                        if not hasattr(request, 'tenant') or not request.tenant:
                            from hub.apps.tenants.models import Tenant
                            try:
                                request.tenant = Tenant.objects.get(id=db_user.tenant_id)
                            except Tenant.DoesNotExist:
                                request.tenant = None
                except User.DoesNotExist:
                    pass
            # Legacy fallback: try to get from user object directly
            elif hasattr(request.user, 'tenant') and request.user.tenant:
                request.tenant_id = str(request.user.tenant.id)
                request.tenant = request.user.tenant
            # Last resort: try to get tenant_id directly from user object
            elif hasattr(request.user, 'tenant_id') and request.user.tenant_id:
                request.tenant_id = str(request.user.tenant_id)
                # Try to get tenant object
                if not hasattr(request, 'tenant') or not request.tenant:
                    from hub.apps.tenants.models import Tenant
                    try:
                        request.tenant = Tenant.objects.get(id=request.user.tenant_id)
                    except Tenant.DoesNotExist:
                        request.tenant = None
        
        return None

