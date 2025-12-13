"""
Comprehensive tests for WebSocket authentication middleware.
"""
import pytest
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.auth.models import APIKey
from hub.apps.tenants.models import Tenant
from hub.apps.websocket.middleware.auth import (
    get_user_from_api_key,
    get_user_from_token,
)

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestWebSocketAuthMiddleware(TestCase):
    """Test WebSocket authentication middleware."""

    def setUp(self):
        """Set up test fixtures."""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
        )

        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

        # Generate JWT token in sync context
        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        self.token = JWTTokenGenerator.generate_access_token(self.user)

    async def test_get_user_from_token_valid(self):
        """Test getting user from valid JWT token."""
        # Token was generated in setUp with user's current token_version
        # The token should work as-is since it was generated with the user's token_version
        user = await get_user_from_token(self.token)

        self.assertIsNotNone(user, "User should be found from valid token")
        if user:
            self.assertEqual(user.id, self.user.id)

    async def test_get_user_from_token_invalid(self):
        """Test getting user from invalid JWT token."""
        user = await get_user_from_token("invalid-token")

        self.assertIsNone(user)

    async def test_get_user_from_api_key_valid(self):
        """Test getting user from valid API key."""
        # Create API key using database_sync_to_async to ensure proper connection handling
        api_key_obj = await database_sync_to_async(APIKey.objects.create)(
            user=self.user,
            name="Test API Key",
            key="test-api-key-valid",
        )

        # Now test async lookup
        user = await get_user_from_api_key(api_key_obj.key)

        self.assertIsNotNone(user)
        self.assertEqual(user.id, self.user.id)

    async def test_get_user_from_api_key_invalid(self):
        """Test getting user from invalid API key."""
        user = await get_user_from_api_key("invalid-key")

        self.assertIsNone(user)

    async def test_get_user_from_api_key_inactive(self):
        """Test getting user from inactive API key."""
        # Create inactive API key using database_sync_to_async to ensure proper connection handling
        api_key_obj = await database_sync_to_async(APIKey.objects.create)(
            user=self.user,
            name="Test API Key",
            key="test-api-key-inactive",
            is_active=False,
        )

        user = await get_user_from_api_key(api_key_obj.key)

        self.assertIsNone(user)
