"""
Comprehensive tests for WebSocket authentication middleware.
"""
import uuid
from datetime import timedelta

import pytest

# Optional channels import
try:
    from channels.db import database_sync_to_async
    CHANNELS_AVAILABLE = True
except ImportError:
    from asgiref.sync import sync_to_async
    database_sync_to_async = sync_to_async
    CHANNELS_AVAILABLE = False

from django.contrib.auth import get_user_model
from django.utils import timezone

# Skip tests if channels not available
pytestmark = pytest.mark.skipif(
    not CHANNELS_AVAILABLE, reason="Django Channels not installed"
)

from hub.apps.auth.models import APIKey
from hub.apps.tenants.models import Tenant
from hub.apps.websocket.middleware.auth import (
    get_user_from_api_key,
    get_user_from_token,
)
from hub.apps.websocket.tests.test_base import AsyncWebSocketTransactionTestCase

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestWebSocketAuthMiddleware(AsyncWebSocketTransactionTestCase):
    """Test WebSocket authentication middleware."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
        )

        self.user = self.create_unique_user(
            tenant=self.tenant,
            password="testpass123",
        )
        self.user.refresh_from_db()

        # Generate JWT token
        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        self.token = JWTTokenGenerator.generate_access_token(self.user)

    async def test_get_user_from_token_valid(self):
        """Test getting user from valid JWT token."""
        user = await get_user_from_token(self.token)

        self.assertIsNotNone(user, "User should be found from valid token")
        self.assertEqual(user.id, self.user.id)

    async def test_get_user_from_token_invalid(self):
        """Test getting user from invalid JWT token."""
        user = await get_user_from_token("invalid-token")

        self.assertIsNone(user)

    async def test_get_user_from_api_key_valid(self):
        """Test getting user from valid API key."""
        plaintext_key = f"test-api-key-valid-{uuid.uuid4().hex[:12]}"
        key_hash = APIKey.hash_key(plaintext_key)
        await database_sync_to_async(APIKey.objects.create)(
            tenant=self.tenant,
            user=self.user,
            name="Test API Key",
            key_hash=key_hash,
        )

        user = await get_user_from_api_key(plaintext_key)

        self.assertIsNotNone(user)
        self.assertEqual(user.id, self.user.id)

    async def test_get_user_from_api_key_invalid(self):
        """Test getting user from invalid API key."""
        user = await get_user_from_api_key("invalid-key")

        self.assertIsNone(user)

    async def test_get_user_from_api_key_inactive(self):
        """Test getting user from expired (inactive) API key."""
        plaintext_key = f"test-api-key-inactive-{uuid.uuid4().hex[:12]}"
        key_hash = APIKey.hash_key(plaintext_key)
        await database_sync_to_async(APIKey.objects.create)(
            tenant=self.tenant,
            user=self.user,
            name="Test API Key",
            key_hash=key_hash,
            expires_at=timezone.now() - timedelta(days=1),
        )

        user = await get_user_from_api_key(plaintext_key)

        self.assertIsNone(user)
