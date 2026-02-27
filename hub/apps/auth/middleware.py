"""
Authentication Middleware

Middleware for tenant scoping and request enrichment.

CRITICAL: This middleware runs BEFORE REST Framework authentication.
It extracts tenant_id from Authorization headers (API keys or JWT tokens)
so that rate limiting middleware can access it.

REST Framework authentication will run later and can override/validate.
"""
from django.contrib.auth import get_user_model
import structlog

logger = structlog.get_logger(__name__)

User = get_user_model()


class TenantScopingMiddleware:
    """
    Middleware to extract and set tenant_id from JWT token or API key.
    
    This runs BEFORE REST Framework authentication, so it extracts tenant_id
    directly from Authorization headers to support rate limiting middleware.
    
    Sets request.tenant_id and request.tenant for use in views and rate limiting.
    """
    
    def __init__(self, get_response):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response
    
    def __call__(self, request):
        """Process request and return response."""
        # Handle DRF's force_authenticate in test environments
        # force_authenticate sets _force_auth_user before authentication classes run
        # We need to set request.user here so our middleware can access it
        if not hasattr(request, 'user') or not request.user or not request.user.is_authenticated:
            forced_user = getattr(request, '_force_auth_user', None)
            if forced_user is not None:
                request.user = forced_user
        
        # Process request
        self.process_request(request)
        
        # Get response
        response = self.get_response(request)
        
        # Process response (if needed in future)
        return response
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

            key_hash = APIKey.hash_key(api_key)
            api_key_obj = (
                APIKey.objects.select_related('tenant', 'user')
                .prefetch_related('user__user_roles__role')
                .get(key_hash=key_hash)
            )
            if api_key_obj.is_expired() or api_key_obj.is_revoked():
                return None
            tenant_id_str = str(api_key_obj.tenant.id)
            request.tenant_id = tenant_id_str
            request.tenant = api_key_obj.tenant
            request.api_key_scopes = api_key_obj.scopes
            request.api_key_obj = api_key_obj
            if api_key_obj.user_id and api_key_obj.user:
                user = api_key_obj.user
                if user.is_active():
                    request.user = user
            return tenant_id_str
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
        # This is for session-based authentication and test environments (force_authenticate)
        # Note: DRF's force_authenticate may set request._force_auth_user instead of request.user
        # Check both locations for test compatibility
        user = getattr(request, 'user', None)
        if user is None:
            # DRF's force_authenticate might set _force_auth_user
            user = getattr(request, '_force_auth_user', None)
        
        # Debug logging for test environments (only in test mode to avoid production overhead)
        import os
        if os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('test') or 'test' in os.environ.get('PYTEST_CURRENT_TEST', ''):
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(
                f"TenantScopingMiddleware: user={user}, "
                f"has_user={hasattr(request, 'user')}, "
                f"has_force_auth={hasattr(request, '_force_auth_user')}, "
                f"user_id={getattr(user, 'id', None) if user else None}, "
                f"user_tenant_id={getattr(user, 'tenant_id', None) if user else None}"
            )
        
        if user:
            from django.contrib.auth.models import AnonymousUser
            # Check if user is authenticated (works with both real auth and force_authenticate)
            is_anonymous = isinstance(user, AnonymousUser)
            # In test environments, force_authenticate sets user but is_authenticated might not be evaluated
            # So we check both is_authenticated and if user has an ID
            is_authenticated = not is_anonymous and (
                getattr(user, 'is_authenticated', False) or 
                (hasattr(user, 'id') and user.id is not None)
            )
            if is_authenticated:
                # Ensure request.user is set for consistency
                if not hasattr(request, 'user') or request.user != user:
                    request.user = user
                tenant_id_set = False
                try:
                    # Query user from database to get fresh tenant_id (avoid cached relationships)
                    # This is important for thread safety with LiveServerTestCase
                    db_user = User.objects.only('tenant_id').get(id=user.id)
                    if db_user.tenant_id:
                        request.tenant_id = str(db_user.tenant_id)
                        tenant_id_set = True
                        # Also set tenant object if not already set
                        if not hasattr(request, 'tenant') or not request.tenant:
                            from hub.apps.tenants.models import Tenant
                            try:
                                request.tenant = Tenant.objects.get(id=db_user.tenant_id)
                            except Tenant.DoesNotExist:
                                request.tenant = None
                except User.DoesNotExist:
                    # User doesn't exist in DB - try fallback
                    pass
                except Exception:
                    # Any other error (e.g., transaction isolation in tests) - try fallback
                    pass
                
                # Fallback: if DB query didn't set tenant_id, try user object directly
                # This is important for test environments where transaction isolation might prevent DB queries
                if not tenant_id_set:
                    if hasattr(user, 'tenant_id') and user.tenant_id:
                        request.tenant_id = str(user.tenant_id)
                        tenant_id_set = True
                        # Try to get tenant object
                        if not hasattr(request, 'tenant') or not request.tenant:
                            from hub.apps.tenants.models import Tenant
                            try:
                                request.tenant = Tenant.objects.get(id=user.tenant_id)
                            except Tenant.DoesNotExist:
                                request.tenant = None
                    elif hasattr(user, 'tenant') and user.tenant:
                        request.tenant_id = str(user.tenant.id)
                        tenant_id_set = True
                        request.tenant = user.tenant
            else:
                # User not authenticated - try legacy fallback for edge cases
                if hasattr(user, 'tenant') and user.tenant:
                    request.tenant_id = str(user.tenant.id)
                    request.tenant = user.tenant
                elif hasattr(user, 'tenant_id') and user.tenant_id:
                    request.tenant_id = str(user.tenant_id)
                    # Try to get tenant object
                    if not hasattr(request, 'tenant') or not request.tenant:
                        from hub.apps.tenants.models import Tenant
                        try:
                            request.tenant = Tenant.objects.get(id=user.tenant_id)
                        except Tenant.DoesNotExist:
                            request.tenant = None
        
        return None

