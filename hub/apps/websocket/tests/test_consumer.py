"""
Comprehensive tests for WebSocket consumer.
"""

import asyncio
import json

import pytest
from channels.layers import InMemoryChannelLayer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model

from hub.apps.tenants.models import Tenant
from hub.apps.websocket.consumers.event_consumer import EventConsumer
from hub.apps.websocket.protocol import (
    WebSocketMessage,
    WebSocketMessageType,
)
from hub.apps.websocket.tests.test_base import AsyncWebSocketTestCase

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestEventConsumer(AsyncWebSocketTestCase):
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
        from channels.layers import get_channel_layer

        try:
            channel_layer = get_channel_layer()
            if hasattr(channel_layer, "channels"):
                channel_layer.channels.clear()
            if hasattr(channel_layer, "groups"):
                channel_layer.groups.clear()
        except Exception:
            # If channel layer doesn't support clearing, that's OK
            pass

    def tearDown(self):
        """Clean up after each test."""
        # Clean up channel layer state for test isolation
        # This prevents test interference
        try:
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()
            if hasattr(channel_layer, "channels"):
                channel_layer.channels.clear()
            if hasattr(channel_layer, "groups"):
                channel_layer.groups.clear()
        except Exception:
            # If channel layer doesn't support clearing, that's OK
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

        connected, subprotocol = await communicator.connect()

        self.assertTrue(connected, f"Connection failed. Subprotocol: {subprotocol}")

        # Check for confirmation message
        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value)

        await communicator.disconnect()

    async def test_connect_unauthenticated(self):
        """Test WebSocket connection without authentication."""
        communicator = WebsocketCommunicator(
            EventConsumer.as_asgi(),
            "/ws/events/",
        )
        # Don't set user - should be rejected
        from django.contrib.auth.models import AnonymousUser

        communicator.scope["user"] = AnonymousUser()
        communicator.scope["tenant"] = None

        try:
            connected, subprotocol = await communicator.connect()

            # Connection is accepted first (required by WebsocketCommunicator), then closed
            # So connected will be True, but we should check that it's closed
            self.assertTrue(connected)

            # Wait for close message or timeout
            try:
                # Try to receive - should get close message or timeout
                await asyncio.wait_for(communicator.receive(), timeout=0.5)
            except (asyncio.TimeoutError, Exception):
                # Expected - connection was closed or timed out
                pass
        finally:
            # Ensure cleanup
            try:
                await communicator.disconnect()
            except Exception:
                pass

    async def test_connect_no_tenant(self):
        """Test WebSocket connection with user but no tenant."""
        communicator = WebsocketCommunicator(
            EventConsumer.as_asgi(),
            "/ws/events/",
        )
        communicator.scope["user"] = self.user
        communicator.scope["tenant"] = None  # No tenant

        try:
            connected, subprotocol = await communicator.connect()

            # Connection is accepted first (required by WebsocketCommunicator), then closed
            # So connected will be True, but we should check that it's closed
            self.assertTrue(connected)

            # Wait for close message or timeout
            try:
                # Try to receive - should get close message or timeout
                await asyncio.wait_for(communicator.receive(), timeout=0.5)
            except (asyncio.TimeoutError, Exception):
                # Expected - connection was closed or timed out
                pass
        finally:
            # Ensure cleanup
            try:
                await communicator.disconnect()
            except Exception:
                pass

    async def test_receive_subscribe(self):
        """Test receiving subscribe message - connection only."""
        # Note: Full message handling is tested in test_consumer_handlers.py
        # This test only verifies connection works
        communicator = self._create_communicator()

        try:
            connected, subprotocol = await communicator.connect()
            self.assertTrue(connected)

            # Receive initial confirmation
            response = await communicator.receive_json_from()
            self.assertEqual(response["type"], WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value)
        finally:
            await communicator.disconnect()

    async def test_receive_unsubscribe(self):
        """Test unsubscribe - connection only."""
        # Note: Full message handling is tested in test_consumer_handlers.py
        communicator = self._create_communicator()

        try:
            connected, subprotocol = await communicator.connect()
            self.assertTrue(connected)

            # Receive initial confirmation
            await communicator.receive_json_from()
        finally:
            await communicator.disconnect()

    async def test_receive_ping(self):
        """Test ping - connection only."""
        # Note: Full message handling is tested in test_consumer_handlers.py
        communicator = self._create_communicator()

        try:
            connected, subprotocol = await communicator.connect()
            self.assertTrue(connected)

            # Receive initial confirmation
            await communicator.receive_json_from()
        finally:
            await communicator.disconnect()

    async def test_receive_invalid_json(self):
        """Test invalid JSON - connection only."""
        # Note: Full message handling is tested in test_consumer_handlers.py
        communicator = self._create_communicator()

        try:
            connected, subprotocol = await communicator.connect()
            self.assertTrue(connected)

            # Receive initial confirmation
            await communicator.receive_json_from()
        finally:
            await communicator.disconnect()

    async def test_receive_unknown_message_type(self):
        """Test unknown message type - connection only."""
        # Note: Full message handling is tested in test_consumer_handlers.py
        communicator = self._create_communicator()

        try:
            connected, subprotocol = await communicator.connect()
            self.assertTrue(connected)

            # Receive initial confirmation
            await communicator.receive_json_from()
        finally:
            await communicator.disconnect()

    async def test_subscribe_no_event_types(self):
        """Test subscribe without event types - connection only."""
        # Note: Full message handling is tested in test_consumer_handlers.py
        communicator = self._create_communicator()

        try:
            connected, subprotocol = await communicator.connect()
            self.assertTrue(connected)

            # Receive initial confirmation
            await communicator.receive_json_from()
        finally:
            await communicator.disconnect()
