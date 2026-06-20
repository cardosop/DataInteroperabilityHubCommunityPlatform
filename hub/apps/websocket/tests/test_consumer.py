"""
Comprehensive tests for WebSocket consumer.
"""

import asyncio
import json

import pytest

# Optional channels imports
try:
    from channels.layers import InMemoryChannelLayer, get_channel_layer
    from channels.testing import WebsocketCommunicator

    CHANNELS_AVAILABLE = True
except ImportError:
    InMemoryChannelLayer = None
    WebsocketCommunicator = None
    get_channel_layer = None
    CHANNELS_AVAILABLE = False

from django.contrib.auth import get_user_model

# Skip tests if channels not available
pytestmark = pytest.mark.skipif(not CHANNELS_AVAILABLE, reason="Django Channels not installed")

import contextlib

from hub.apps.websocket.consumers.event_consumer import EventConsumer
from hub.apps.websocket.protocol import (
    WebSocketMessage,
    WebSocketMessageType,
)
from hub.apps.websocket.tests.test_base import AsyncWebSocketTransactionTestCase

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestEventConsumer(AsyncWebSocketTransactionTestCase):
    """Test EventConsumer class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create tenant with unique name/slug to avoid conflicts
        self.tenant = self.create_unique_tenant(status="ACTIVE")

        # Create user with unique email to avoid conflicts
        self.user = self.create_unique_user(
            tenant=self.tenant,
            password="testpass123",
        )

        # Ensure clean channel layer state for each test
        # This prevents test isolation issues
        if not CHANNELS_AVAILABLE:
            return

        try:
            channel_layer = get_channel_layer()
            if hasattr(channel_layer, "channels"):
                channel_layer.channels.clear()
            if hasattr(channel_layer, "groups"):
                channel_layer.groups.clear()
        except (AttributeError, NotImplementedError):
            # In-memory channel layer or test layer without flush support
            pass

    def tearDown(self):
        """Clean up after each test."""
        try:
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()
            if hasattr(channel_layer, "channels"):
                channel_layer.channels.clear()
            if hasattr(channel_layer, "groups"):
                channel_layer.groups.clear()
        except (AttributeError, NotImplementedError):
            # In-memory channel layer or test layer without flush support
            pass

    def _create_communicator(self):
        """Create WebSocket communicator with authenticated user."""
        # Create a fresh communicator for each test to ensure isolation
        communicator = WebsocketCommunicator(
            EventConsumer.as_asgi(),
            "/ws/events/",
        )
        # Manually set user and tenant in scope (bypassing middleware for direct testing)
        communicator.scope["user"] = self.user
        communicator.scope["tenant"] = self.tenant
        return communicator

    async def test_connect_authenticated(self):
        """Test WebSocket connection with authenticated user."""
        communicator = self._create_communicator()

        try:
            connected, subprotocol = await communicator.connect()
            self.assertTrue(connected, f"Connection failed. Subprotocol: {subprotocol}")

            # Check for confirmation message
            response = await communicator.receive_json_from()
            self.assertEqual(response["type"], WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value)
        finally:
            await communicator.disconnect()

    async def test_connect_unauthenticated(self):
        """Test WebSocket connection without authentication — connection is
        accepted by ASGI but the consumer MUST close it immediately."""
        communicator = WebsocketCommunicator(
            EventConsumer.as_asgi(),
            "/ws/events/",
        )
        from django.contrib.auth.models import AnonymousUser

        communicator.scope["user"] = AnonymousUser()
        communicator.scope["tenant"] = None

        try:
            connected, _subprotocol = await communicator.connect()
            # ASGI always accepts the connection first; the consumer
            # should then close it immediately for unauthenticated users.
            self.assertTrue(connected)

            # The consumer calls accept() then close(code=4001) for AnonymousUser.
            close_frame = await asyncio.wait_for(communicator.receive_output(), timeout=2.0)
            self.assertEqual(close_frame["type"], "websocket.close")
            self.assertEqual(close_frame.get("code"), 4001)
        finally:
            await communicator.disconnect()

    async def test_connect_no_tenant(self):
        """Test WebSocket connection with user but no tenant — the consumer
        sends an error message and closes with code 4003 (Forbidden)."""
        communicator = WebsocketCommunicator(
            EventConsumer.as_asgi(),
            "/ws/events/",
        )
        communicator.scope["user"] = self.user
        communicator.scope["tenant"] = None

        try:
            connected, _subprotocol = await communicator.connect()
            self.assertTrue(connected)

            # The consumer first sends a JSON error via websocket.send,
            # then closes with code 4003.
            error_response = await asyncio.wait_for(
                communicator.receive_json_from(), timeout=2.0
            )
            self.assertEqual(error_response["type"], "error")
            self.assertIn("tenant", error_response.get("error", "").lower())

            close_frame = await asyncio.wait_for(
                communicator.receive_output(), timeout=2.0
            )
            self.assertEqual(close_frame["type"], "websocket.close")
            self.assertEqual(close_frame.get("code"), 4003)
        finally:
            await communicator.disconnect()

    async def test_receive_subscribe(self):
        """Test receiving subscribe message - connection only."""
        # Note: Full message handling is tested in test_consumer_handlers.py
        # This test only verifies connection works
        communicator = self._create_communicator()

        try:
            connected, _subprotocol = await communicator.connect()
            self.assertTrue(connected)

            # Receive initial confirmation
            response = await communicator.receive_json_from()
            self.assertEqual(response["type"], WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value)
        finally:
            await communicator.disconnect()

    async def test_receive_unsubscribe(self):
        """Test unsubscribe after subscribing to events."""
        communicator = self._create_communicator()

        try:
            connected, _subprotocol = await communicator.connect()
            self.assertTrue(connected)

            # Receive initial confirmation
            await communicator.receive_json_from()

            # First subscribe to some event types
            subscribe_msg = WebSocketMessage(
                type=WebSocketMessageType.SUBSCRIBE.value,
                data={"event_types": ["asset.created", "asset.updated"]},
            )
            await communicator.send_json_to(json.loads(subscribe_msg.to_json()))

            # Receive subscription confirmation
            sub_response = await communicator.receive_json_from()
            self.assertEqual(
                sub_response["type"], WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value
            )
            self.assertIn("asset.created", sub_response["data"]["event_types"])

            # Now unsubscribe from one event type
            unsubscribe_msg = WebSocketMessage(
                type=WebSocketMessageType.UNSUBSCRIBE.value,
                data={"event_types": ["asset.created"]},
            )
            await communicator.send_json_to(json.loads(unsubscribe_msg.to_json()))

            # Receive unsubscribe confirmation
            unsub_response = await communicator.receive_json_from()
            self.assertEqual(
                unsub_response["type"], WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value
            )
            self.assertNotIn("asset.created", unsub_response["data"]["event_types"])
            self.assertIn("asset.updated", unsub_response["data"]["event_types"])
        finally:
            await communicator.disconnect()

    async def test_receive_ping(self):
        """Test ping message receives a pong response."""
        communicator = self._create_communicator()

        try:
            connected, _subprotocol = await communicator.connect()
            self.assertTrue(connected)

            # Receive initial confirmation
            await communicator.receive_json_from()

            # Send a ping message
            ping_msg = WebSocketMessage(
                type=WebSocketMessageType.PING.value,
                timestamp="2026-03-26T00:00:00Z",
            )
            await communicator.send_json_to(json.loads(ping_msg.to_json()))

            # Expect a pong response
            response = await communicator.receive_json_from()
            self.assertEqual(response["type"], WebSocketMessageType.PONG.value)
        finally:
            await communicator.disconnect()

    async def test_receive_invalid_json(self):
        """Test invalid JSON sends an error response."""
        communicator = self._create_communicator()

        try:
            connected, _subprotocol = await communicator.connect()
            self.assertTrue(connected)

            # Receive initial confirmation
            await communicator.receive_json_from()

            # Send invalid JSON as raw text
            await communicator.send_to(text_data="this is not valid json{{{")

            # Expect an error response
            response = await communicator.receive_json_from()
            self.assertEqual(response["type"], WebSocketMessageType.ERROR.value)
            self.assertIn("Invalid JSON", response["error"])
        finally:
            await communicator.disconnect()

    async def test_receive_unknown_message_type(self):
        """Test unknown message type sends an error response."""
        communicator = self._create_communicator()

        try:
            connected, _subprotocol = await communicator.connect()
            self.assertTrue(connected)

            # Receive initial confirmation
            await communicator.receive_json_from()

            # Send a message with an unknown type
            unknown_msg = WebSocketMessage(
                type="totally_unknown_type",
                data={"foo": "bar"},
            )
            await communicator.send_json_to(json.loads(unknown_msg.to_json()))

            # Expect an error response about unknown message type
            response = await communicator.receive_json_from()
            self.assertEqual(response["type"], WebSocketMessageType.ERROR.value)
            self.assertIn("Unknown message type", response["error"])
        finally:
            await communicator.disconnect()

    async def test_subscribe_no_event_types(self):
        """Test subscribe with empty event_types sends an error."""
        communicator = self._create_communicator()

        try:
            connected, _subprotocol = await communicator.connect()
            self.assertTrue(connected)

            # Receive initial confirmation
            await communicator.receive_json_from()

            # Send subscribe with empty event_types list
            subscribe_msg = WebSocketMessage(
                type=WebSocketMessageType.SUBSCRIBE.value,
                data={"event_types": []},
            )
            await communicator.send_json_to(json.loads(subscribe_msg.to_json()))

            # Expect an error about no event types
            response = await communicator.receive_json_from()
            self.assertEqual(response["type"], WebSocketMessageType.ERROR.value)
            self.assertIn("No event types", response["error"])
        finally:
            await communicator.disconnect()
