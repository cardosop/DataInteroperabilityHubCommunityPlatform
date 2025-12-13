"""
Comprehensive tests for WebSocket authentication middleware.
"""

import pytest
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TestCase

from hub.apps.auth.models import APIKey
from hub.apps.tenants.models import Tenant
from hub.apps.websocket.middleware.auth import (
    get_user_from_api_key,
    get_user_from_token,
)

User = get_user_model()


@pytest.mark.django_db(transaction=False)
class TestWebSocketAuthMiddleware(TestCase):
    """Test WebSocket authentication middleware."""

    def setUp(self):
        """Set up test fixtures."""
        # #region agent log
        import json
        import threading
        import time

        try:
            with open("/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A",
                            "location": "test_middleware.py:setUp:entry",
                            "message": "setUp entry",
                            "data": {
                                "thread_id": threading.get_ident(),
                                "thread_name": threading.current_thread().name,
                            },
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion
        # Ensure database connection is open and properly initialized
        # This is critical for database_sync_to_async in async tests
        # We need to ensure the connection is available in the thread
        # that database_sync_to_async uses
        connection = connections["default"]
        # #region agent log
        try:
            conn_state = {
                "has_connection": connection.connection is not None,
                "connection_closed": (
                    hasattr(connection.connection, "closed") and connection.connection.closed
                    if connection.connection
                    else None
                ),
                "thread_id": threading.get_ident(),
            }
            with open("/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A",
                            "location": "test_middleware.py:setUp:before_ensure",
                            "message": "Connection state before ensure_connection",
                            "data": conn_state,
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion
        if connection.connection is None or (
            hasattr(connection.connection, "closed") and connection.connection.closed
        ):
            connection.close()
        connection.ensure_connection()

        # #region agent log
        try:
            conn_state_after = {
                "has_connection": connection.connection is not None,
                "connection_closed": (
                    hasattr(connection.connection, "closed") and connection.connection.closed
                    if connection.connection
                    else None
                ),
                "thread_id": threading.get_ident(),
            }
            with open("/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A",
                            "location": "test_middleware.py:setUp:after_ensure",
                            "message": "Connection state after ensure_connection",
                            "data": conn_state_after,
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

        # Force a query to ensure the connection is fully initialized
        # This helps ensure the connection is available in async contexts
        try:
            User.objects.first()
        except Exception:
            pass

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

        # #region agent log
        try:
            with open("/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "B",
                            "location": "test_middleware.py:setUp:user_created",
                            "message": "User created",
                            "data": {
                                "user_id": str(self.user.id),
                                "thread_id": threading.get_ident(),
                            },
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

        # Refresh user from database to ensure it's in sync
        # This ensures the user object has the latest data from the database
        self.user.refresh_from_db()

        # Generate JWT token in sync context
        # This ensures the token is generated with the user's current token_version
        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        self.token = JWTTokenGenerator.generate_access_token(self.user)

        # Verify the token can be decoded (sanity check)
        payload = JWTTokenGenerator.decode_access_token(self.token)
        assert payload is not None, "Token should be decodable"
        assert payload.get("sub") == str(self.user.id), "Token should contain user ID"

        # #region agent log
        try:
            with open("/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A",
                            "location": "test_middleware.py:setUp:exit",
                            "message": "setUp exit",
                            "data": {
                                "user_id": str(self.user.id),
                                "thread_id": threading.get_ident(),
                            },
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

    async def test_get_user_from_token_valid(self):
        """Test getting user from valid JWT token."""
        # #region agent log
        import json
        import threading
        import time

        try:
            with open("/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A",
                            "location": "test_middleware.py:test_get_user_from_token_valid:entry",
                            "message": "Test entry",
                            "data": {
                                "thread_id": threading.get_ident(),
                                "thread_name": threading.current_thread().name,
                            },
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

        # Initialize database connection by querying the user with database_sync_to_async
        # This is similar to how API key tests work - they create the API key using
        # database_sync_to_async which initializes the connection properly.
        # By querying the user here, we ensure the connection is initialized in the
        # async test context before we try to get the user from the token.
        user_exists = await database_sync_to_async(
            lambda: User.objects.filter(id=self.user.id).exists()
        )()
        self.assertTrue(user_exists, "User should exist in database")

        # Token was generated in setUp with user's current token_version
        # The token should work as-is since it was generated with the user's token_version
        # database_sync_to_async will handle connection management automatically
        user = await get_user_from_token(self.token)

        # #region agent log
        try:
            with open("/home/ph/Desktop/DataInteroperabilityHub/.cursor/debug.log", "a") as f:
                f.write(
                    json.dumps(
                        {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "A",
                            "location": "test_middleware.py:test_get_user_from_token_valid:after_call",
                            "message": "After get_user_from_token call",
                            "data": {
                                "user_found": user is not None,
                                "user_id": str(user.id) if user else None,
                                "expected_user_id": str(self.user.id),
                                "thread_id": threading.get_ident(),
                            },
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

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
        # database_sync_to_async will handle connection management automatically
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
        # database_sync_to_async will handle connection management automatically
        api_key_obj = await database_sync_to_async(APIKey.objects.create)(
            user=self.user,
            name="Test API Key",
            key="test-api-key-inactive",
            is_active=False,
        )

        user = await get_user_from_api_key(api_key_obj.key)

        self.assertIsNone(user)
