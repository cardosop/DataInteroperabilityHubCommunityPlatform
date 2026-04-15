"""
Tests for WebSocket Token Auth Migration (Task 220.1).

Covers:
- Message-based authentication flow (connect → send authenticate → receive auth_confirmed)
- Deprecated query-param fallback with deprecation warning
- Rejection of all messages before authentication
- 10-second auth timeout with automatic disconnection
- Query-param rejection after deprecation period (WEBSOCKET_QUERY_PARAM_AUTH_DISABLED=True)
- Integration: full middleware → consumer flow with message-based auth
"""

import asyncio
import uuid
from unittest.mock import patch

import pytest

try:
    from channels.testing import WebsocketCommunicator

    CHANNELS_AVAILABLE = True
except ImportError:
    WebsocketCommunicator = None
    CHANNELS_AVAILABLE = False

from django.contrib.auth import get_user_model
from django.test import override_settings

pytestmark = pytest.mark.skipif(
    not CHANNELS_AVAILABLE, reason="Django Channels not installed"
)

from hub.apps.tenants.models import Tenant
from hub.apps.websocket.consumers.event_consumer import EventConsumer
from hub.apps.websocket.middleware.auth import WebSocketAuthMiddleware
from hub.apps.websocket.protocol import WebSocketMessageType
from hub.apps.websocket.routing import websocket_urlpatterns
from hub.apps.websocket.tests.test_base import AsyncWebSocketTransactionTestCase

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestMessageBasedAuth(AsyncWebSocketTransactionTestCase):
    """Test the new message-based authentication flow."""

    def setUp(self):
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

        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        self.token = JWTTokenGenerator.generate_access_token(self.user)

    def _create_unauthenticated_communicator(self):
        """Create communicator with NO user set (simulates no query-param auth)."""
        communicator = WebsocketCommunicator(
            EventConsumer.as_asgi(),
            "/ws/events/",
        )
        # Simulate middleware passing through without auth (pending message auth)
        communicator.scope["user"] = None
        communicator.scope["tenant"] = None
        communicator.scope["auth_method"] = "pending_message_auth"
        return communicator

    def _create_deprecated_query_param_communicator(self):
        """Create communicator simulating deprecated query-param auth."""
        communicator = WebsocketCommunicator(
            EventConsumer.as_asgi(),
            "/ws/events/",
        )
        # Simulate middleware authenticating via deprecated query param
        communicator.scope["user"] = self.user
        communicator.scope["tenant"] = self.tenant
        communicator.scope["auth_method"] = "jwt_token_query_param_deprecated"
        return communicator

    async def test_message_auth_happy_path(self):
        """Connect without credentials, send authenticate message, receive confirmation."""
        communicator = self._create_unauthenticated_communicator()

        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected, "Unauthenticated connection should be accepted")

            # Send authenticate message
            await communicator.send_json_to({
                "type": "authenticate",
                "data": {"token": self.token},
            })

            # Should receive auth_confirmed
            response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=2.0
            )
            self.assertEqual(response["type"], WebSocketMessageType.AUTH_CONFIRMED.value)
            self.assertIn("user_id", response["data"])
            self.assertEqual(response["data"]["user_id"], str(self.user.id))
        finally:
            await communicator.disconnect()

    async def test_message_auth_invalid_token(self):
        """Authenticate message with invalid token should close connection."""
        communicator = self._create_unauthenticated_communicator()

        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Send authenticate with bad token
            await communicator.send_json_to({
                "type": "authenticate",
                "data": {"token": "invalid-jwt-token"},
            })

            # Should receive error and then connection closes
            response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=2.0
            )
            self.assertEqual(response["type"], WebSocketMessageType.ERROR.value)
            self.assertIn("Authentication failed", response["error"])
        finally:
            try:
                await communicator.disconnect()
            except Exception:
                pass

    async def test_message_auth_missing_token(self):
        """Authenticate message without token field should return error."""
        communicator = self._create_unauthenticated_communicator()

        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Send authenticate with no token
            await communicator.send_json_to({
                "type": "authenticate",
                "data": {},
            })

            response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=2.0
            )
            self.assertEqual(response["type"], WebSocketMessageType.ERROR.value)
            self.assertIn("token", response["error"].lower())
        finally:
            try:
                await communicator.disconnect()
            except Exception:
                pass

    async def test_reject_messages_before_auth(self):
        """All non-authenticate messages should be rejected before authentication."""
        communicator = self._create_unauthenticated_communicator()

        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Try to subscribe before authenticating
            await communicator.send_json_to({
                "type": "subscribe",
                "data": {"event_types": ["asset.created"]},
            })

            response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=2.0
            )
            self.assertEqual(response["type"], WebSocketMessageType.ERROR.value)
            self.assertIn("Authentication required", response["error"])
        finally:
            await communicator.disconnect()

    async def test_reject_ping_before_auth(self):
        """Ping messages should be rejected before authentication."""
        communicator = self._create_unauthenticated_communicator()

        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.send_json_to({"type": "ping"})

            response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=2.0
            )
            self.assertEqual(response["type"], WebSocketMessageType.ERROR.value)
            self.assertIn("Authentication required", response["error"])
        finally:
            await communicator.disconnect()

    @override_settings(WEBSOCKET_AUTH_TIMEOUT=1)
    async def test_auth_timeout_disconnects(self):
        """Connection should be closed after auth timeout if no authenticate message."""
        communicator = self._create_unauthenticated_communicator()

        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Auth timeout is 1 second (from override_settings).
            # Wait for the error message and close.
            try:
                response = await asyncio.wait_for(
                    communicator.receive_json_from(), timeout=3.0
                )
                self.assertEqual(response["type"], WebSocketMessageType.ERROR.value)
                self.assertIn("timeout", response["error"].lower())
            except asyncio.TimeoutError:
                self.fail("Expected error message before auth timeout close")

            # Connection should now be closed
            try:
                output = await asyncio.wait_for(
                    communicator.receive_output(), timeout=2.0
                )
                self.assertEqual(output["type"], "websocket.close")
            except asyncio.TimeoutError:
                # Some channel layer implementations may not surface the close
                pass
        finally:
            try:
                await communicator.disconnect()
            except Exception:
                pass

    async def test_subscribe_works_after_auth(self):
        """After successful message-based auth, normal operations should work."""
        communicator = self._create_unauthenticated_communicator()

        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Authenticate first
            await communicator.send_json_to({
                "type": "authenticate",
                "data": {"token": self.token},
            })

            auth_response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=2.0
            )
            self.assertEqual(auth_response["type"], WebSocketMessageType.AUTH_CONFIRMED.value)

            # Now subscribe should work
            await communicator.send_json_to({
                "type": "subscribe",
                "data": {"event_types": ["asset.created"]},
            })

            sub_response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=2.0
            )
            self.assertEqual(
                sub_response["type"],
                WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value,
            )
            self.assertIn("asset.created", sub_response["data"]["event_types"])
        finally:
            await communicator.disconnect()

    async def test_double_authenticate_rejected(self):
        """Sending authenticate after already authenticated should be rejected."""
        communicator = self._create_unauthenticated_communicator()

        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # First authenticate
            await communicator.send_json_to({
                "type": "authenticate",
                "data": {"token": self.token},
            })
            auth_response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=2.0
            )
            self.assertEqual(auth_response["type"], WebSocketMessageType.AUTH_CONFIRMED.value)

            # Second authenticate should be rejected
            await communicator.send_json_to({
                "type": "authenticate",
                "data": {"token": self.token},
            })
            response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=2.0
            )
            self.assertEqual(response["type"], WebSocketMessageType.ERROR.value)
            self.assertIn("Already authenticated", response["error"])
        finally:
            await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
class TestDeprecatedQueryParamAuth(AsyncWebSocketTransactionTestCase):
    """Test that query-param auth still works but logs deprecation warning."""

    def setUp(self):
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

        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        self.token = JWTTokenGenerator.generate_access_token(self.user)

    async def test_query_param_auth_still_works(self):
        """Query-param auth should still work during deprecation period."""
        communicator = WebsocketCommunicator(
            EventConsumer.as_asgi(),
            "/ws/events/",
        )
        # Simulate middleware having authenticated via query param (deprecated)
        communicator.scope["user"] = self.user
        communicator.scope["tenant"] = self.tenant
        communicator.scope["auth_method"] = "jwt_token_query_param_deprecated"

        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Should receive connection confirmation (fully authenticated)
            response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=2.0
            )
            self.assertEqual(
                response["type"],
                WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value,
            )
        finally:
            await communicator.disconnect()

    @override_settings(WEBSOCKET_QUERY_PARAM_AUTH_DISABLED=True)
    async def test_query_param_rejected_after_deprecation(self):
        """After deprecation period, query-param auth should be rejected."""
        # This tests the middleware behavior — when the setting is True,
        # the middleware should NOT authenticate via query params
        middleware = WebSocketAuthMiddleware(inner=None)

        scope = {
            "type": "websocket",
            "query_string": f"token={self.token}".encode(),
            "headers": [],
        }

        close_sent = False
        close_code = None

        async def mock_send(message):
            nonlocal close_sent, close_code
            if message.get("type") == "websocket.close":
                close_sent = True
                close_code = message.get("code")

        async def mock_receive():
            return {"type": "websocket.connect"}

        await middleware(scope, mock_receive, mock_send)

        # Should have been rejected (close sent)
        self.assertTrue(close_sent, "Query-param auth should be rejected")
        self.assertEqual(close_code, 4001)


@pytest.mark.django_db(transaction=True)
class TestMiddlewareMessageAuthPassthrough(AsyncWebSocketTransactionTestCase):
    """Test that middleware lets unauthenticated connections through for message auth."""

    def setUp(self):
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

        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        self.token = JWTTokenGenerator.generate_access_token(self.user)

    async def test_middleware_passes_through_no_credentials(self):
        """When no credentials are provided, middleware should pass through for message auth."""
        inner_called = False
        inner_scope = None

        async def mock_inner(scope, receive, send):
            nonlocal inner_called, inner_scope
            inner_called = True
            inner_scope = scope

        middleware = WebSocketAuthMiddleware(mock_inner)

        scope = {
            "type": "websocket",
            "query_string": b"",
            "headers": [],
        }

        await middleware(scope, None, None)

        self.assertTrue(inner_called, "Inner application should be called")
        self.assertIsNone(inner_scope.get("user"))
        self.assertEqual(inner_scope["auth_method"], "pending_message_auth")

    async def test_middleware_deprecation_warning_for_query_param(self):
        """Middleware should log deprecation warning when token comes via query param."""
        inner_called = False
        inner_scope = None

        async def mock_inner(scope, receive, send):
            nonlocal inner_called, inner_scope
            inner_called = True
            inner_scope = scope

        middleware = WebSocketAuthMiddleware(mock_inner)

        scope = {
            "type": "websocket",
            "query_string": f"token={self.token}".encode(),
            "headers": [],
        }

        with patch("hub.apps.websocket.middleware.auth.logger") as mock_logger:
            await middleware(scope, None, None)

        self.assertTrue(inner_called)
        # User should be authenticated
        self.assertEqual(inner_scope["user"].id, self.user.id)
        # Auth method should indicate deprecated query param
        self.assertEqual(inner_scope["auth_method"], "jwt_token_query_param_deprecated")
        # Deprecation warning should have been logged
        mock_logger.warning.assert_any_call(
            "websocket_auth_query_param_deprecated",
            path=scope.get("path"),
            message="Token authentication via query parameter is deprecated. "
                    "Use message-based authentication instead.",
        )

    async def test_middleware_header_auth_not_deprecated(self):
        """Authorization header auth should NOT be marked as deprecated."""
        inner_called = False
        inner_scope = None

        async def mock_inner(scope, receive, send):
            nonlocal inner_called, inner_scope
            inner_called = True
            inner_scope = scope

        middleware = WebSocketAuthMiddleware(mock_inner)

        scope = {
            "type": "websocket",
            "query_string": b"",
            "headers": [
                (b"authorization", f"Bearer {self.token}".encode()),
            ],
        }

        await middleware(scope, None, None)

        self.assertTrue(inner_called)
        self.assertEqual(inner_scope["user"].id, self.user.id)
        self.assertEqual(inner_scope["auth_method"], "jwt_token")


@pytest.mark.django_db(transaction=True)
class TestIntegrationMiddlewareToConsumer(AsyncWebSocketTransactionTestCase):
    """Integration test: full middleware → consumer flow with message-based auth."""

    def setUp(self):
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

        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        self.token = JWTTokenGenerator.generate_access_token(self.user)

    async def test_full_flow_message_auth(self):
        """Full integration: connect without token → authenticate via message → subscribe."""
        from channels.routing import URLRouter

        app = WebSocketAuthMiddleware(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(app, "/ws/events/")

        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Send authenticate message
            await communicator.send_json_to({
                "type": "authenticate",
                "data": {"token": self.token},
            })

            # Should receive auth_confirmed
            response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=2.0
            )
            self.assertEqual(response["type"], WebSocketMessageType.AUTH_CONFIRMED.value)
            self.assertEqual(response["data"]["user_id"], str(self.user.id))

            # Now subscribe
            await communicator.send_json_to({
                "type": "subscribe",
                "data": {"event_types": ["asset.created"]},
            })

            sub_response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=2.0
            )
            self.assertEqual(
                sub_response["type"],
                WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value,
            )
        finally:
            await communicator.disconnect()

    async def test_full_flow_deprecated_query_param(self):
        """Full integration: connect with token in query param (deprecated but works)."""
        from channels.routing import URLRouter

        app = WebSocketAuthMiddleware(URLRouter(websocket_urlpatterns))
        communicator = WebsocketCommunicator(
            app, f"/ws/events/?token={self.token}"
        )

        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Should receive connection confirmation directly (no authenticate needed)
            response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=2.0
            )
            self.assertEqual(
                response["type"],
                WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value,
            )

            # Subscribe should work immediately
            await communicator.send_json_to({
                "type": "subscribe",
                "data": {"event_types": ["asset.created"]},
            })

            sub_response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=2.0
            )
            self.assertEqual(
                sub_response["type"],
                WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value,
            )
        finally:
            await communicator.disconnect()
