"""
Comprehensive tests for enhanced WebSocket authentication middleware.

Tests token extraction from query params and headers, validation, and connection rejection.
"""
import asyncio
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import connections
from hub.apps.websocket.tests.test_base import AsyncWebSocketTestCase
from channels.db import database_sync_to_async

import pytest

from hub.apps.auth.models import APIKey
from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.tenants.models import Tenant
from hub.apps.websocket.middleware.auth import (
    WebSocketAuthMiddleware,
    get_user_from_token,
    get_user_from_api_key,
)

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestWebSocketAuthEnhancement(AsyncWebSocketTestCase):
    """Test enhanced WebSocket authentication middleware."""

    def setUp(self):
        """Set up test fixtures."""
        # Ensure database connection is open and properly initialized
        # This is critical for database_sync_to_async in async tests
        connection = connections["default"]
        if connection.connection is None or (
            hasattr(connection.connection, "closed") and connection.connection.closed
        ):
            connection.close()
        connection.ensure_connection()

        # Create tenant with unique name/slug to avoid conflicts
        self.tenant = self.create_unique_tenant(status="ACTIVE")

        # Create user with unique email to avoid conflicts
        self.user = self.create_unique_user(
            tenant=self.tenant,
            password="testpass123",
        )

        # Refresh user from database to ensure it's in sync
        self.user.refresh_from_db()

        # Generate JWT token
        self.token = JWTTokenGenerator.generate_access_token(self.user)

        # Verify the token can be decoded (sanity check)
        payload = JWTTokenGenerator.decode_access_token(self.token)
        assert payload is not None, "Token should be decodable"
        assert payload.get("sub") == str(self.user.id), "Token should contain user ID"

        # Create API key with unique plaintext key to avoid hash conflicts
        import uuid
        self.plaintext_api_key = f"test-api-key-{uuid.uuid4().hex[:8]}"
        key_hash = APIKey.hash_key(self.plaintext_api_key)
        self.api_key_obj = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Test API Key",
            key_hash=key_hash,
        )

    def _run_async_test(self, async_func):
        """Helper to run async tests with proper database connection handling."""
        from django.db import close_old_connections
        close_old_connections()

        async def wrapped():
            close_old_connections()
            return await async_func()

        return asyncio.run(wrapped())

    async def _test_middleware_auth(self, scope, should_authenticate=True):
        """Helper to test middleware authentication."""
        next_called = False

        async def next_middleware(scope, receive, send):
            nonlocal next_called
            next_called = True

        middleware = WebSocketAuthMiddleware(next_middleware)

        messages = []
        async def send(message):
            messages.append(message)

        async def receive():
            return {"type": "websocket.connect"}

        await middleware(scope, receive, send)

        if should_authenticate:
            # Should be authenticated - check that next middleware was called
            # and user is set correctly
            if not next_called:
                return False
            user = scope.get("user")
            if user is None:
                return False
            if isinstance(user, AnonymousUser):
                return False
            if user.id != self.user.id:
                return False
            return True
        else:
            # Should be rejected - check that close message was sent
            # and next middleware was NOT called
            if next_called:
                return False
            if len(messages) == 0:
                return False
            close_message = messages[0]
            if close_message.get("type") != "websocket.close":
                return False
            if close_message.get("code") != 4001:
                return False
            return True

    def test_middleware_extracts_token_from_query_params(self):
        """Test that middleware extracts JWT token from query parameters."""
        async def run_test():
            scope = {
                "type": "websocket",
                "path": "/ws/events/",
                "query_string": b"token=" + self.token.encode("utf-8"),
                "headers": [],
            }
            return await self._test_middleware_auth(scope, should_authenticate=True)

        result = self._run_async_test(run_test)
        self.assertTrue(result)

    def test_middleware_extracts_token_from_headers(self):
        """Test that middleware extracts JWT token from Authorization header."""
        async def run_test():
            scope = {
                "type": "websocket",
                "path": "/ws/events/",
                "query_string": b"",
                "headers": [
                    (b"authorization", b"Bearer " + self.token.encode("utf-8")),
                ],
            }
            return await self._test_middleware_auth(scope, should_authenticate=True)

        result = self._run_async_test(run_test)
        self.assertTrue(result)

    def test_middleware_extracts_token_from_access_token_query_param(self):
        """Test that middleware extracts token from access_token query parameter."""
        async def run_test():
            scope = {
                "type": "websocket",
                "path": "/ws/events/",
                "query_string": b"access_token=" + self.token.encode("utf-8"),
                "headers": [],
            }
            return await self._test_middleware_auth(scope, should_authenticate=True)

        result = self._run_async_test(run_test)
        self.assertTrue(result)

    def test_middleware_rejects_invalid_token(self):
        """Test that middleware rejects connection with invalid token."""
        async def run_test():
            scope = {
                "type": "websocket",
                "path": "/ws/events/",
                "query_string": b"token=invalid-token-12345",
                "headers": [],
            }
            return await self._test_middleware_auth(scope, should_authenticate=False)

        result = self._run_async_test(run_test)
        self.assertTrue(result)

    def test_middleware_rejects_missing_token(self):
        """Test that middleware rejects connection without token."""
        async def run_test():
            scope = {
                "type": "websocket",
                "path": "/ws/events/",
                "query_string": b"",
                "headers": [],
            }
            return await self._test_middleware_auth(scope, should_authenticate=False)

        result = self._run_async_test(run_test)
        self.assertTrue(result)

    def test_middleware_extracts_api_key_from_query_params(self):
        """Test that middleware extracts API key from query parameters."""
        async def run_test():
            scope = {
                "type": "websocket",
                "path": "/ws/events/",
                "query_string": b"api_key=" + self.plaintext_api_key.encode("utf-8"),
                "headers": [],
            }
            return await self._test_middleware_auth(scope, should_authenticate=True)

        result = self._run_async_test(run_test)
        self.assertTrue(result)

    def test_middleware_extracts_api_key_from_headers(self):
        """Test that middleware extracts API key from X-API-Key header."""
        async def run_test():
            scope = {
                "type": "websocket",
                "path": "/ws/events/",
                "query_string": b"",
                "headers": [
                    (b"x-api-key", self.plaintext_api_key.encode("utf-8")),
                ],
            }
            return await self._test_middleware_auth(scope, should_authenticate=True)

        result = self._run_async_test(run_test)
        self.assertTrue(result)

    def test_middleware_rejects_invalid_api_key(self):
        """Test that middleware rejects connection with invalid API key."""
        async def run_test():
            scope = {
                "type": "websocket",
                "path": "/ws/events/",
                "query_string": b"api_key=invalid-key-12345",
                "headers": [],
            }
            return await self._test_middleware_auth(scope, should_authenticate=False)

        result = self._run_async_test(run_test)
        self.assertTrue(result)

    def test_middleware_rejects_expired_api_key(self):
        """Test that middleware rejects connection with expired API key."""
        from django.utils import timezone
        from datetime import timedelta

        # Create expired API key
        expired_key_plaintext = "expired-key-12345"
        expired_key_hash = APIKey.hash_key(expired_key_plaintext)
        expired_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Expired Key",
            key_hash=expired_key_hash,
            expires_at=timezone.now() - timedelta(days=1),  # Expired yesterday
        )

        async def run_test():
            scope = {
                "type": "websocket",
                "path": "/ws/events/",
                "query_string": b"api_key=" + expired_key_plaintext.encode("utf-8"),
                "headers": [],
            }
            return await self._test_middleware_auth(scope, should_authenticate=False)

        result = self._run_async_test(run_test)
        self.assertTrue(result)

    def test_middleware_prefers_jwt_over_api_key(self):
        """Test that middleware prefers JWT token over API key when both are provided."""
        # Ensure database connection is available before async call
        from django.db import close_old_connections
        close_old_connections()

        async def run_test():
            # Close old connections and ensure fresh connection in async context
            from django.db import close_old_connections
            close_old_connections()

            scope = {
                "type": "websocket",
                "path": "/ws/events/",
                "query_string": (
                    b"token=" + self.token.encode("utf-8") +
                    b"&api_key=" + self.plaintext_api_key.encode("utf-8")
                ),
                "headers": [],
            }
            return await self._test_middleware_auth(scope, should_authenticate=True)

        result = self._run_async_test(run_test)
        self.assertTrue(result)

    def test_middleware_extracts_tenant_from_user(self):
        """Test that middleware extracts tenant from authenticated user."""
        async def run_test():
            scope = {
                "type": "websocket",
                "path": "/ws/events/",
                "query_string": b"token=" + self.token.encode("utf-8"),
                "headers": [],
            }

            async def next_middleware(scope, receive, send):
                pass  # Next middleware doesn't need to do anything

            middleware = WebSocketAuthMiddleware(next_middleware)

            messages = []
            async def send(message):
                messages.append(message)

            async def receive():
                return {"type": "websocket.connect"}

            await middleware(scope, receive, send)

            tenant = scope.get("tenant")
            if tenant is None:
                return False, "Tenant should be extracted from user"
            if tenant.id != self.tenant.id:
                return False, f"Tenant ID mismatch: expected {self.tenant.id}, got {tenant.id}"
            return True, None

        result, error = self._run_async_test(run_test)
        if error:
            self.fail(error)
        self.assertTrue(result)

    def test_middleware_handles_malformed_authorization_header(self):
        """Test that middleware handles malformed Authorization header gracefully."""
        async def run_test():
            scope = {
                "type": "websocket",
                "path": "/ws/events/",
                "query_string": b"",
                "headers": [
                    (b"authorization", b"InvalidFormat token123"),
                ],
            }
            return await self._test_middleware_auth(scope, should_authenticate=False)

        result = self._run_async_test(run_test)
        self.assertTrue(result)

    def test_middleware_handles_url_encoded_tokens(self):
        """Test that middleware handles URL-encoded tokens correctly."""
        import urllib.parse

        async def run_test():
            encoded_token = urllib.parse.quote(self.token)
            scope = {
                "type": "websocket",
                "path": "/ws/events/",
                "query_string": b"token=" + encoded_token.encode("utf-8"),
                "headers": [],
            }
            return await self._test_middleware_auth(scope, should_authenticate=True)

        result = self._run_async_test(run_test)
        self.assertTrue(result)

    def test_get_user_from_token_valid(self):
        """Test get_user_from_token with valid token."""
        async def run_test():
            # Initialize database connection by querying the user with database_sync_to_async
            # This ensures the connection is initialized in the async context
            user_exists = await database_sync_to_async(
                lambda: User.objects.filter(id=self.user.id).exists()
            )()
            if not user_exists:
                return None, "User should exist in database"

            # Now test async lookup
            user = await get_user_from_token(self.token)
            return user, None

        # Run async test in sync context
        user, error = self._run_async_test(run_test)
        if error:
            self.fail(error)
        self.assertIsNotNone(user, "User should be found from valid token")
        self.assertEqual(user.id, self.user.id)

    def test_get_user_from_token_invalid(self):
        """Test get_user_from_token with invalid token."""
        async def run_test():
            return await get_user_from_token("invalid-token")

        user = self._run_async_test(run_test)
        self.assertIsNone(user, "Invalid token should return None")

    def test_get_user_from_api_key_valid(self):
        """Test get_user_from_api_key with valid API key."""
        async def run_test():
            # Initialize database connection
            api_key_exists = await database_sync_to_async(
                lambda: APIKey.objects.filter(id=self.api_key_obj.id).exists()
            )()
            if not api_key_exists:
                return None, "API key should exist in database"

            # Now test async lookup
            user = await get_user_from_api_key(self.plaintext_api_key)
            return user, None

        # Run async test in sync context
        user, error = self._run_async_test(run_test)
        if error:
            self.fail(error)
        self.assertIsNotNone(user, "User should be found from valid API key")
        self.assertEqual(user.id, self.user.id)

    def test_get_user_from_api_key_invalid(self):
        """Test get_user_from_api_key with invalid API key."""
        async def run_test():
            return await get_user_from_api_key("invalid-key")

        user = self._run_async_test(run_test)
        self.assertIsNone(user, "Invalid API key should return None")
