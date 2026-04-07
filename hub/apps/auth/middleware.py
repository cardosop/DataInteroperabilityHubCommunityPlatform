"""
Authentication Middleware

Middleware for tenant scoping and request enrichment.

CRITICAL: This middleware runs BEFORE REST Framework authentication.
It extracts tenant_id from Authorization headers (API keys or JWT tokens)
so that rate limiting middleware can access it.

REST Framework authentication will run later and can override/validate.
"""
from django.contrib.auth.models import AnonymousUser
from django.db import OperationalError, DatabaseError
from django.http import HttpResponse
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
        
        # Process request; short-circuit if middleware returns HttpResponse (e.g. 403)
        response = self.process_request(request)
        if response is not None:
            return response
        
        return self.get_response(request)
    
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
            # Set worker_authenticated flag if the API key has an internal scope,
            # so WorkerInternalAPIPermission passes even when DRF auth classes
            # are skipped (because middleware already set request.user).
            internal_scopes = {"scheduled_ingestion:internal", "scheduled_export:internal"}
            if internal_scopes & set(api_key_obj.scopes or []):
                request.worker_authenticated = True
            if api_key_obj.user_id and api_key_obj.user:
                user = api_key_obj.user
                if user.is_active():
                    request.user = user
            return tenant_id_str
        except APIKey.DoesNotExist:
            # Invalid API key - will be caught by REST Framework authentication
            return None
        except (ValueError, TypeError, KeyError, AttributeError) as e:
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
            # Lightweight decode without version check (for tenant extraction only).
            # Full validation happens in REST Framework authentication.
            payload = JWTTokenGenerator.decode_access_token(token, verify_version=False)
            if payload and 'tenant_id' in payload:
                return payload.get('tenant_id')
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            # Log but don't fail - let REST Framework authentication handle errors
            logger.debug("failed_to_extract_tenant_from_jwt", error=str(e))
            return None
        
        return None
    
    def process_request(self, request):
        """
        Extract tenant_id from Authorization header or request.user.
        
        Priority:
        1. X-Tenant-Id header (if present): validate membership; set tenant or 403
        2. If tenant_id already set, use it
        3. Extract from API key in Authorization header (for rate limiting)
        4. Extract from JWT token in Authorization header (for rate limiting)
        5. Get from request.user (set by Django's AuthenticationMiddleware)
        
        This ensures tenant_id is available for rate limiting middleware
        even though REST Framework authentication hasn't run yet.
        """
        # X-Tenant-Id: validate membership and set tenant or return 403
        x_tenant_id = request.META.get("HTTP_X_TENANT_ID", "").strip()
        if x_tenant_id:
            from django.conf import settings

            if not getattr(settings, "FEATURE_TENANT_SWITCH_ENABLED", True):
                return HttpResponse(status=403)
            user = getattr(request, "user", None) or getattr(request, "_force_auth_user", None)
            is_anon = user is None or isinstance(user, AnonymousUser)
            # When user not in request (e.g. JWT/ApiKey before DRF auth), try to resolve
            if is_anon:
                auth_header = request.META.get("HTTP_AUTHORIZATION", "")
                if auth_header.startswith("Bearer "):
                    token = auth_header.split(" ", 1)[1] if " " in auth_header else None
                    if token:
                        try:
                            from hub.apps.auth.jwt_utils import JWTTokenGenerator

                            payload = JWTTokenGenerator.decode_access_token(token, verify_version=False)
                            if payload:
                                user = JWTTokenGenerator.get_user_from_token(payload)
                                if user and user.is_active():
                                    request.user = user
                                    is_anon = False
                        except (ValueError, TypeError, KeyError, AttributeError):
                            pass
                elif auth_header.startswith("ApiKey "):
                    # Lightweight API key lookup to resolve user before DRF auth
                    tenant_id_from_key = self._extract_tenant_id_from_api_key(request)
                    if tenant_id_from_key:
                        user = getattr(request, "user", None)
                        if user and not isinstance(user, AnonymousUser):
                            is_anon = False
            is_authenticated = (
                not is_anon
                and (getattr(user, "is_authenticated", False) or (hasattr(user, "id") and user.id is not None))
            )
            if not is_authenticated:
                # Return 401 (not 403) when X-Tenant-Id is present but the bearer
                # token is missing/expired/invalid. Semantics: 401 = "your
                # credentials are invalid, refresh them"; 403 = "your credentials
                # are valid but you lack permission". Returning 403 here breaks
                # the frontend's automatic refresh-on-401 → retry path, which
                # would otherwise transparently re-auth on token expiry.
                return HttpResponse(status=401)
            # Allow if user's own tenant matches, or if explicit membership exists
            user_tenant_id = str(getattr(user, "tenant_id", None) or "")
            if user_tenant_id != str(x_tenant_id):
                from hub.apps.users.services import UserTenantMembershipService
                if not UserTenantMembershipService().validate_membership(user, x_tenant_id):
                    return HttpResponse(status=403)
            from hub.apps.tenants.models import Tenant

            try:
                tenant = Tenant.objects.get(id=x_tenant_id)
                request.tenant_id = str(tenant.id)
                request.tenant = tenant
            except Tenant.DoesNotExist:
                return HttpResponse(status=403)
            return None

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
            except Tenant.DoesNotExist:
                from django.http import JsonResponse
                return JsonResponse({"error": "TENANT_NOT_FOUND"}, status=403)
            except (OperationalError, DatabaseError):
                from django.http import JsonResponse
                return JsonResponse({"error": "SERVICE_UNAVAILABLE"}, status=503)
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
            except Tenant.DoesNotExist:
                from django.http import JsonResponse
                return JsonResponse({"error": "TENANT_NOT_FOUND"}, status=403)
            except (OperationalError, DatabaseError):
                from django.http import JsonResponse
                return JsonResponse({"error": "SERVICE_UNAVAILABLE"}, status=503)
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
                except (OperationalError, DatabaseError):
                    # DB connectivity issue — try fallback from user object
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

