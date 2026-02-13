"""
Authentication Service

Service layer for API key operations.
All create/update/delete paths apply validation and audit.
"""

from datetime import timedelta
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone

from hub.apps.audit.utils import create_audit_event
from hub.apps.core.services.base import BaseService, NotFoundError, ValidationError

from .models import APIKey


class APIKeyService(BaseService):
    """
    Service for API key operations.

    Provides business logic for:
    - API key creation with validation and audit
    - API key update
    - API key deletion
    """

    service_name = "api_key_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        self.tenant_id = tenant_id
        self.user_id = user_id

    @transaction.atomic
    def create_api_key(
        self,
        tenant_id: str,
        user_id: Optional[str],
        name: str,
        scopes: Optional[list] = None,
        expires_in_days: Optional[int] = None,
        rate_limit_per_hour: Optional[int] = None,
    ) -> tuple[APIKey, str]:
        """
        Create an API key with validation and audit.

        Args:
            tenant_id: Tenant ID
            user_id: Optional user ID (for user-scoped keys)
            name: API key name
            scopes: Optional list of scopes
            expires_in_days: Optional expiration in days
            rate_limit_per_hour: Optional rate limit

        Returns:
            Tuple of (APIKey instance, plaintext_key)

        Raises:
            ValidationError: If validation fails
        """
        from django.contrib.auth import get_user_model

        from hub.apps.tenants.models import Tenant

        User = get_user_model()

        # Get tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise NotFoundError(f"Tenant {tenant_id} not found")

        # Get user if provided
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id, tenant_id=tenant_id)
            except User.DoesNotExist:
                raise NotFoundError(f"User {user_id} not found")

        # Generate API key
        plaintext_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(plaintext_key)

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = timezone.now() + timedelta(days=expires_in_days)

        # Create API key
        api_key = APIKey.objects.create(
            tenant=tenant,
            user=user,
            key_hash=key_hash,
            name=name,
            scopes=scopes or [],
            expires_at=expires_at,
            rate_limit_per_hour=rate_limit_per_hour,
        )

        # Store plaintext key temporarily for response (not saved to DB)
        api_key._plaintext_key = plaintext_key

        # Create audit event
        from django.contrib.auth import get_user_model

        User = get_user_model()
        actor_user = None
        if self.user_id or user_id:
            try:
                actor_user = User.objects.get(id=self.user_id or user_id)
            except User.DoesNotExist:
                pass

        create_audit_event(
            resource_type="API_KEY",
            action="API_KEY_CREATED",
            actor_user=actor_user,
            tenant=tenant,
            resource_id=str(api_key.id),
            details={
                "name": name,
                "scopes": scopes,
                "expires_at": expires_at.isoformat() if expires_at else None,
            },
        )

        return api_key, plaintext_key

    @transaction.atomic
    def delete_api_key(
        self,
        api_key_id: str,
        tenant_id: str,
        actor_user_id: str,
    ) -> None:
        """
        Delete an API key with audit.

        Args:
            api_key_id: API key ID
            tenant_id: Tenant ID
            actor_user_id: User ID performing the deletion

        Raises:
            NotFoundError: If API key not found
        """
        # Get API key
        api_key = self.get_resource_or_raise(
            APIKey,
            api_key_id,
            tenant_id=tenant_id,
        )

        # Create audit event before deletion
        from django.contrib.auth import get_user_model

        User = get_user_model()
        actor_user = None
        if actor_user_id:
            try:
                actor_user = User.objects.get(id=actor_user_id)
            except User.DoesNotExist:
                pass

        create_audit_event(
            resource_type="API_KEY",
            action="API_KEY_DELETED",
            actor_user=actor_user,
            tenant=api_key.tenant,
            resource_id=str(api_key.id),
            details={"name": api_key.name},
        )

        # Delete API key
        api_key.delete()
