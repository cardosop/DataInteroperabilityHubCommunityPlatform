"""
Authentication Classes

JWT and API Key authentication for REST API.
"""
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model

from .jwt_utils import JWTTokenGenerator
from .models import APIKey

User = get_user_model()


class JWTAuthentication(BaseAuthentication):
    """
    JWT Authentication implementation.
    
    Authenticates requests using JWT Bearer tokens in the Authorization header.
    """
    
    def authenticate(self, request):
        """
        Authenticate the request using JWT tokens.
        
        Returns (user, token) tuple if authentication succeeds, None otherwise.
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        
        # Decode token
        payload = JWTTokenGenerator.decode_access_token(token)
        if not payload:
            raise AuthenticationFailed('Invalid or expired token')
        
        # Get user
        user = JWTTokenGenerator.get_user_from_token(payload)
        if not user:
            raise AuthenticationFailed('User not found')
        
        # Check if user is active
        if not user.is_active():
            raise AuthenticationFailed('User is not active')
        
        # Validate token version
        if not JWTTokenGenerator.validate_token_version(payload, user):
            raise AuthenticationFailed('Token has been invalidated')
        
        # Store tenant_id in request for middleware
        request.tenant_id = payload.get('tenant_id')
        request.token_payload = payload
        
        return (user, token)
    
    def authenticate_header(self, request):
        """Return the WWW-Authenticate header value."""
        return 'Bearer'


class APIKeyAuthentication(BaseAuthentication):
    """
    API Key Authentication implementation.
    
    Authenticates requests using API keys in the Authorization header or X-API-Key header.
    """
    
    def authenticate(self, request):
        """
        Authenticate the request using API keys.
        
        Returns (user, key) tuple if authentication succeeds, None otherwise.
        """
        # Check Authorization header first
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        api_key = None
        
        if auth_header.startswith('ApiKey '):
            api_key = auth_header.split(' ')[1]
        else:
            # Check X-API-Key header
            api_key = request.META.get('HTTP_X_API_KEY')
        
        if not api_key:
            return None
        
        # Hash the provided key
        key_hash = APIKey.hash_key(api_key)
        
        # Look up API key
        try:
            api_key_obj = APIKey.objects.get(key_hash=key_hash)
        except APIKey.DoesNotExist:
            raise AuthenticationFailed('Invalid API key')
        
        # Check if expired
        if api_key_obj.is_expired():
            raise AuthenticationFailed('API key has expired')
        
        # Update last used timestamp
        api_key_obj.update_last_used()
        
        # Get user (if user-scoped) or create a system user
        if api_key_obj.user:
            user = api_key_obj.user
            if not user.is_active():
                raise AuthenticationFailed('User is not active')
            # Refresh user from DB to get fresh tenant_id (critical for thread safety with LiveServerTestCase)
            # This ensures we have the latest tenant_id from the database, not from a cached object
            user.refresh_from_db(fields=['tenant_id', 'tenant'])
        else:
            # Tenant-scoped API key without user - create a system user representation
            # For now, we'll use the tenant's first admin or create a system user
            # This is a simplified approach - in production, you might want a dedicated system user
            raise AuthenticationFailed('User-scoped API keys are required')
        
        # Store tenant_id and scopes in request
        # CRITICAL: Use tenant_id from API key object (fresh from DB) to ensure thread safety
        # Also ensure user.tenant_id is set for fallback scenarios
        # Convert to string for consistency (some code expects string UUIDs)
        tenant_id_str = str(api_key_obj.tenant.id)
        request.tenant_id = tenant_id_str
        request.api_key_scopes = api_key_obj.scopes
        request.api_key_obj = api_key_obj
        # Also set tenant object for views that use request.tenant
        # Refresh tenant from DB to ensure it's fresh (important for thread safety)
        api_key_obj.tenant.refresh_from_db()
        request.tenant = api_key_obj.tenant
        
        # CRITICAL: Ensure user.tenant_id is also set for views that check user.tenant_id
        # This is a fallback in case request.tenant_id isn't accessible
        if not hasattr(user, 'tenant_id') or user.tenant_id != api_key_obj.tenant.id:
            # Refresh user to ensure tenant_id matches
            user.refresh_from_db(fields=['tenant_id'])
        
        return (user, api_key)
    
    def authenticate_header(self, request):
        """Return the WWW-Authenticate header value."""
        return 'ApiKey'

