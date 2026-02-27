"""
JWT Token Generation and Validation Utilities

Handles creation and validation of JWT access tokens.
"""
import uuid

import jwt
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class JWTTokenGenerator:
    """
    JWT Token Generator for access tokens.
    
    Generates JWT tokens with standard and custom claims including
    tenant_id, roles, and token version for invalidation.
    """
    
    @staticmethod
    def generate_access_token(
        user: User,
        tenant_id: Optional[str] = None,
        roles: Optional[list] = None,
        scopes: Optional[list] = None
    ) -> str:
        """
        Generate a JWT access token for a user.
        
        Args:
            user: User instance
            tenant_id: Tenant UUID (optional, will use user.tenant.id if not provided)
            roles: List of role names (optional, will fetch from user if not provided)
            scopes: List of scopes (optional)
        
        Returns:
            Encoded JWT token string
        """
        now = timezone.now()
        exp = now + timedelta(seconds=settings.JWT_ACCESS_TOKEN_EXPIRY)
        
        # Get tenant_id
        if tenant_id is None:
            tenant_id = str(user.tenant.id) if user.tenant else None
        
        # Get roles if not provided
        if roles is None:
            roles = []
            if hasattr(user, 'user_roles'):
                roles = [ur.role.name for ur in user.user_roles.all()]
        
        # Standard claims
        payload: Dict[str, Any] = {
            'iss': settings.JWT_ISSUER if hasattr(settings, 'JWT_ISSUER') else 'hub',
            'sub': str(user.id),
            'aud': ['idh-api-v1'],
            'exp': int(exp.timestamp()),
            'iat': int(now.timestamp()),
            'nbf': int(now.timestamp()),
            'jti': str(uuid.uuid4()),  # Unique per token for refresh rotation
        }
        
        # Custom claims
        if tenant_id:
            payload['tenant_id'] = tenant_id
            if user.tenant:
                payload['tenant_slug'] = user.tenant.slug
        
        payload['email'] = user.email
        if user.display_name:
            payload['name'] = user.display_name
        
        if roles:
            payload['roles'] = roles
        
        if scopes:
            payload['scopes'] = scopes
        
        # Token version for invalidation
        payload['authz_version'] = user.token_version
        
        # Sign and encode token
        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        return token
    
    @staticmethod
    def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Decode and validate a JWT access token.
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded payload dict if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                audience="idh-api-v1",
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @staticmethod
    def validate_token_version(payload: Dict[str, Any], user: User) -> bool:
        """
        Validate that the token version matches the user's current token version.
        
        Args:
            payload: Decoded JWT payload
            user: User instance
        
        Returns:
            True if token version is valid, False otherwise
        """
        if payload is None:
            return False
        token_version = payload.get('authz_version', 0)
        return token_version == user.token_version
    
    @staticmethod
    def get_user_from_token(payload: Dict[str, Any]) -> Optional[User]:
        """
        Get user from JWT token payload.
        
        Args:
            payload: Decoded JWT payload
        
        Returns:
            User instance if found, None otherwise
        """
        if payload is None:
            return None
        user_id = payload.get('sub')
        if not user_id:
            return None
        
        try:
            # CRITICAL: For LiveServerTestCase, ensure we're using a fresh database connection
            # and explicitly select_for_update to ensure we see committed data
            # This is important because LiveServerTestCase runs in a separate thread/process
            from django.db import connection
            connection.ensure_connection()
            
            # Ensure we're using the default database connection
            # In async tests, we need to make sure we're querying the right database
            # Refresh the connection to ensure we see the latest data
            from django.db import connections
            connection = connections['default']
            connection.ensure_connection()
            
            # Query user with explicit connection
            user = User.objects.using('default').get(id=user_id)
            # Refresh from DB to ensure we have the latest data
            user.refresh_from_db()
            return user
        except User.DoesNotExist:
            return None

