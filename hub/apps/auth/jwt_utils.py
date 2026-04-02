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
        
        # Sign and encode token.
        # RS256: use the private key (api-service); HS256: use the shared secret.
        _sign_key = (
            settings.JWT_PRIVATE_KEY
            if settings.JWT_ALGORITHM == "RS256"
            else settings.JWT_SECRET_KEY
        )
        token = jwt.encode(
            payload,
            _sign_key,
            algorithm=settings.JWT_ALGORITHM
        )
        
        return token
    
    @staticmethod
    def decode_access_token(token: str, *, verify_version: bool = True) -> Optional[Dict[str, Any]]:
        """
        Decode and validate a JWT access token.

        When *verify_version* is True (default), the token's ``authz_version``
        claim is checked against the user's current ``token_version`` in the
        database **atomically** — no caller can obtain a decoded payload without
        the version check having run.

        Args:
            token: JWT token string
            verify_version: If True, validate token version against DB (default True).
                Set to False only for lightweight pre-auth extraction (e.g. tenant scoping).

        Returns:
            Decoded payload dict if valid, None otherwise
        """
        try:
            _verify_key = (
                settings.JWT_PUBLIC_KEY
                if settings.JWT_ALGORITHM == "RS256"
                else settings.JWT_SECRET_KEY
            )
            payload = jwt.decode(
                token,
                _verify_key,
                algorithms=[settings.JWT_ALGORITHM],
                audience="idh-api-v1",
            )
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

        if verify_version:
            if not JWTTokenGenerator._validate_token_version(payload):
                return None

        return payload

    @staticmethod
    def _validate_token_version(payload: Dict[str, Any]) -> bool:
        """
        Validate that the token version matches the user's current token version.

        Private — called atomically inside decode_access_token().
        """
        if payload is None:
            return False
        user_id = payload.get('sub')
        if not user_id:
            return False
        try:
            db_version = User.objects.values_list(
                'token_version', flat=True
            ).get(id=user_id)
        except User.DoesNotExist:
            return False
        token_version = payload.get('authz_version', 0)
        return token_version == db_version

    @staticmethod
    def validate_token_version(payload: Dict[str, Any], user: 'User') -> bool:
        """Backward-compatible public wrapper. Prefer decode_access_token(verify_version=True)."""
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
            # Fetch user with all related data in a single query (11.6: eliminate N+1).
            # select_related("tenant") avoids a second query for tenant access.
            # prefetch_related("user_roles__role") avoids N queries when building
            # the roles list in generate_access_token / _build_me_response.
            user = (
                User.objects
                .select_related("tenant")
                .prefetch_related("user_roles__role")
                .get(id=user_id)
            )
            return user
        except User.DoesNotExist:
            return None

