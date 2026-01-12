"""
API Key Manager for API Gateway

Validates API keys using Django ORM to access the database.
"""
import os
import sys
from typing import Optional, Dict, Any
import hashlib
import structlog

# Setup Django before importing models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

import django
django.setup()

from django.utils import timezone
from hub.apps.auth.models import APIKey
from hub.apps.tenants.models import Tenant

logger = structlog.get_logger(__name__)


class APIKeyInfo:
    """Information about a validated API key"""

    def __init__(
        self,
        api_key_id: str,
        tenant_id: str,
        user_id: Optional[str],
        tier: str = 'FREE',
        scopes: Optional[list] = None,
        name: str = ''
    ):
        self.api_key_id = api_key_id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.tier = tier
        self.scopes = scopes if scopes is not None else []
        self.name = name


class APIKeyManager:
    """
    Manages API key validation and lookup.

    Uses Django ORM to access the database for API key validation.
    """

    @staticmethod
    def hash_key(key: str) -> str:
        """
        Hash an API key using SHA-256.

        Args:
            key: Plaintext API key

        Returns:
            SHA-256 hash of the key
        """
        return hashlib.sha256(key.encode()).hexdigest()

    def validate_api_key(self, api_key: str) -> Optional[APIKeyInfo]:
        """
        Validate an API key and return information about it.

        Args:
            api_key: Plaintext API key from request

        Returns:
            APIKeyInfo if valid, None if invalid
        """
        if not api_key:
            return None

        try:
            # Hash the provided key
            key_hash = self.hash_key(api_key)

            # Look up API key in database
            try:
                api_key_obj = APIKey.objects.select_related('tenant', 'user').get(key_hash=key_hash)
            except APIKey.DoesNotExist:
                logger.warning("api_key_not_found", key_hash=key_hash[:16] + "...")
                return None

            # Check if expired
            if api_key_obj.is_expired():
                logger.warning("api_key_expired", api_key_id=str(api_key_obj.id))
                return None

            # Check if tenant is active
            if not api_key_obj.tenant.is_active():
                logger.warning("tenant_inactive", tenant_id=str(api_key_obj.tenant.id))
                return None

            # Get tier from API key (for now, default to FREE if not set)
            # TODO: When tier model is created in task 9.11.1.2.1, use that
            tier = getattr(api_key_obj, 'tier', None)
            if tier is None:
                # Default to FREE tier for now
                tier = 'FREE'
            else:
                tier = str(tier).upper()

            # Update last used timestamp (async, don't block)
            try:
                api_key_obj.update_last_used()
            except Exception as e:
                logger.warning("api_key_last_used_update_failed", error=str(e))

            return APIKeyInfo(
                api_key_id=str(api_key_obj.id),
                tenant_id=str(api_key_obj.tenant.id),
                user_id=str(api_key_obj.user.id) if api_key_obj.user else None,
                tier=tier,
                scopes=api_key_obj.scopes if api_key_obj.scopes is not None else [],
                name=api_key_obj.name
            )

        except Exception as e:
            logger.error("api_key_validation_error", error=str(e))
            return None

    def get_api_key_info(self, api_key_id: str) -> Optional[APIKeyInfo]:
        """
        Get API key information by ID (without validation).

        Args:
            api_key_id: API key UUID

        Returns:
            APIKeyInfo if found, None if not found
        """
        try:
            api_key_obj = APIKey.objects.select_related('tenant', 'user').get(id=api_key_id)

            # Get tier from API key (for now, default to FREE if not set)
            tier = getattr(api_key_obj, 'tier', None)
            if tier is None:
                tier = 'FREE'
            else:
                tier = str(tier).upper()

            return APIKeyInfo(
                api_key_id=str(api_key_obj.id),
                tenant_id=str(api_key_obj.tenant.id),
                user_id=str(api_key_obj.user.id) if api_key_obj.user else None,
                tier=tier,
                scopes=api_key_obj.scopes if api_key_obj.scopes is not None else [],
                name=api_key_obj.name
            )
        except APIKey.DoesNotExist:
            return None
        except Exception as e:
            logger.error("api_key_info_error", api_key_id=api_key_id, error=str(e))
            return None
