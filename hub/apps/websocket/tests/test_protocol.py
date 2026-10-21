"""
Comprehensive tests for WebSocket protocol.
"""

import json

from django.test import TestCase

from hub.apps.websocket.protocol import (
    EventMessage,
    SubscribeMessage,
    WebSocketMessage,
    WebSocketMessageType,
)


class TestWebSocketMessage(TestCase):
    """Test WebSocketMessage class."""

    def test_to_json(self):
        """Test converting message to JSON."""
        message = WebSocketMessage(
            type=WebSocketMessageType.SUBSCRIBE.value,
            data={"event_types": ["contract.created"]},
        )

        json_str = message.to_json()
        data = json.loads(json_str)

        self.assertEqual(data["type"], WebSocketMessageType.SUBSCRIBE.value)
        self.assertEqual(data["data"]["event_types"], ["contract.created"])

    def test_from_json(self):
        """Test creating message from JSON."""
        json_str = json.dumps(
            {
                "type": WebSocketMessageType.SUBSCRIBE.value,
                "data": {"event_types": ["contract.created"]},
            }
        )

        message = WebSocketMessage.from_json(json_str)

        self.assertEqual(message.type, WebSocketMessageType.SUBSCRIBE.value)
        self.assertEqual(message.data["event_types"], ["contract.created"])

    def test_from_json_with_error(self):
        """Test creating message from JSON with error."""
        json_str = json.dumps(
            {
                "type": WebSocketMessageType.ERROR.value,
                "error": "Invalid request",
            }
        )

        message = WebSocketMessage.from_json(json_str)

        self.assertEqual(message.type, WebSocketMessageType.ERROR.value)
        self.assertEqual(message.error, "Invalid request")


class TestSubscribeMessage(TestCase):
    """Test SubscribeMessage class."""

    def test_to_dict(self):
        """Test converting subscribe message to dict."""
        message = SubscribeMessage(
            event_types=["contract.created", "asset.created"],
            filters={"tenant_id": "123"},
        )

        data = message.to_dict()

        self.assertEqual(data["event_types"], ["contract.created", "asset.created"])
        self.assertEqual(data["filters"]["tenant_id"], "123")

    def test_to_dict_no_filters(self):
        """Test converting subscribe message to dict without filters."""
        message = SubscribeMessage(event_types=["contract.created"])

        data = message.to_dict()

        self.assertEqual(data["event_types"], ["contract.created"])
        self.assertNotIn("filters", data)

    def test_from_dict(self):
        """Test creating subscribe message from dict."""
        data = {
            "event_types": ["contract.created"],
            "filters": {"tenant_id": "123"},
        }

        message = SubscribeMessage.from_dict(data)

        self.assertEqual(message.event_types, ["contract.created"])
        self.assertEqual(message.filters["tenant_id"], "123")


class TestEventMessage(TestCase):
    """Test EventMessage class."""

    def test_to_dict(self):
        """Test converting event message to dict."""
        event = EventMessage(
            event_id="123",
            event_type="contract.created",
            event_version="1.0.0",
            timestamp="2025-01-15T10:00:00Z",
            source={"service": "hub", "tenant_id": "456"},
            data={"contract_id": "789"},
            metadata={"correlation_id": "abc"},
        )

        data = event.to_dict()

        self.assertEqual(data["event_id"], "123")
        self.assertEqual(data["event_type"], "contract.created")
        self.assertEqual(data["data"]["contract_id"], "789")
        self.assertEqual(data["metadata"]["correlation_id"], "abc")

    def test_to_dict_no_metadata(self):
        """Test converting event message to dict without metadata."""
        event = EventMessage(
            event_id="123",
            event_type="contract.created",
            event_version="1.0.0",
            timestamp="2025-01-15T10:00:00Z",
            source={"service": "hub"},
            data={"contract_id": "789"},
        )

        data = event.to_dict()

        self.assertEqual(data["event_id"], "123")
        self.assertNotIn("metadata", data)

    def test_from_dict(self):
        """Test creating event message from dict."""
        data = {
            "event_id": "123",
            "event_type": "contract.created",
            "event_version": "1.0.0",
            "timestamp": "2025-01-15T10:00:00Z",
            "source": {"service": "hub"},
            "data": {"contract_id": "789"},
        }

        event = EventMessage.from_dict(data)

        self.assertEqual(event.event_id, "123")
        self.assertEqual(event.event_type, "contract.created")
        self.assertEqual(event.data["contract_id"], "789")
