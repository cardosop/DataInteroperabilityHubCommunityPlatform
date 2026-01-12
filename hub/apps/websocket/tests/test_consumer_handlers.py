"""
Unit tests for WebSocket consumer message handlers.

These tests directly test the consumer's message handling methods
without relying on the full WebSocket connection flow.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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
class TestEventConsumerHandlers(AsyncWebSocketTestCase):
    """Test EventConsumer message handlers directly."""

    def setUp(self):
        """Set up test fixtures."""
        # Create tenant with unique name/slug to avoid conflicts
        self.tenant = self.create_unique_tenant(status="ACTIVE")

        # Create user with unique email to avoid conflicts
        self.user = self.create_unique_user(
            tenant=self.tenant,
            password="testpass123",
        )

    def _create_consumer(self):
        """Create a consumer instance with mocked scope."""
        consumer = EventConsumer()
        consumer.scope = {
            "user": self.user,
            "tenant": self.tenant,
        }
        consumer.send = AsyncMock()
        return consumer

    async def test_handle_subscribe(self):
        """Test handle_subscribe method."""
        consumer = self._create_consumer()

        message = WebSocketMessage(
            type=WebSocketMessageType.SUBSCRIBE.value,
            data={
                "event_types": ["contract.created", "asset.activated"],
                "filters": {},
            },
        )

        await consumer.handle_subscribe(message)

        # Check that event types were subscribed
        self.assertIn("contract.created", consumer.subscribed_event_types)
        self.assertIn("asset.activated", consumer.subscribed_event_types)

        # Check that confirmation was sent
        self.assertTrue(consumer.send.called)
        call_args = consumer.send.call_args
        self.assertIsNotNone(call_args)
        # The send method should have been called with text_data containing JSON
        self.assertIn("text_data", call_args.kwargs)

    async def test_handle_subscribe_no_event_types(self):
        """Test handle_subscribe with no event types."""
        consumer = self._create_consumer()

        message = WebSocketMessage(
            type=WebSocketMessageType.SUBSCRIBE.value,
            data={},
        )

        await consumer.handle_subscribe(message)

        # Should send error
        self.assertTrue(consumer.send.called)

    async def test_handle_unsubscribe(self):
        """Test handle_unsubscribe method."""
        consumer = self._create_consumer()
        consumer.subscribed_event_types = {"contract.created", "asset.activated"}

        message = WebSocketMessage(
            type=WebSocketMessageType.UNSUBSCRIBE.value,
            data={"event_types": ["contract.created"]},
        )

        await consumer.handle_unsubscribe(message)

        # Check that event type was unsubscribed
        self.assertNotIn("contract.created", consumer.subscribed_event_types)
        self.assertIn("asset.activated", consumer.subscribed_event_types)

    async def test_handle_ping(self):
        """Test handle_ping method."""
        consumer = self._create_consumer()

        message = WebSocketMessage(
            type=WebSocketMessageType.PING.value,
            timestamp="2025-01-15T10:00:00Z",
        )

        await consumer.handle_ping(message)

        # Check that pong was sent
        self.assertTrue(consumer.send.called)
        call_args = consumer.send.call_args
        self.assertIsNotNone(call_args)
        self.assertIn("text_data", call_args.kwargs)

    async def test_receive_subscribe_message(self):
        """Test receive method with subscribe message."""
        consumer = self._create_consumer()
        consumer.handle_subscribe = AsyncMock()

        message_json = '{"type": "subscribe", "data": {"event_types": ["contract.created"]}}'

        await consumer.receive(text_data=message_json)

        # Check that handle_subscribe was called
        self.assertTrue(consumer.handle_subscribe.called)

    async def test_receive_ping_message(self):
        """Test receive method with ping message."""
        consumer = self._create_consumer()
        consumer.handle_ping = AsyncMock()

        message_json = '{"type": "ping", "timestamp": "2025-01-15T10:00:00Z"}'

        await consumer.receive(text_data=message_json)

        # Check that handle_ping was called
        self.assertTrue(consumer.handle_ping.called)

    async def test_receive_invalid_json(self):
        """Test receive method with invalid JSON."""
        consumer = self._create_consumer()
        consumer.send_error = AsyncMock()

        await consumer.receive(text_data="invalid json{")

        # Check that error was sent
        self.assertTrue(consumer.send_error.called)
        self.assertIn("Invalid JSON", str(consumer.send_error.call_args))

    async def test_receive_unknown_message_type(self):
        """Test receive method with unknown message type."""
        consumer = self._create_consumer()
        consumer.send_error = AsyncMock()

        message_json = '{"type": "unknown_type", "data": {}}'

        await consumer.receive(text_data=message_json)

        # Check that error was sent
        self.assertTrue(consumer.send_error.called)

