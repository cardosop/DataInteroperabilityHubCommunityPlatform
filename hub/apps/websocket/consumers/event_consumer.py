"""
Event Consumer

WebSocket consumer for real-time event updates.
"""
import json
from typing import Set

import structlog
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from hub.apps.core.events.bus import get_event_bus
from hub.apps.websocket.protocol import (
    EventMessage,
    SubscribeMessage,
    WebSocketMessage,
    WebSocketMessageType,
)

logger = structlog.get_logger(__name__)


class EventConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time event updates.

    Supports:
    - Subscribing to event types
    - Filtering events by tenant and other criteria
    - Real-time event delivery
    """

    def __init__(self, *args, **kwargs):
        """Initialize consumer."""
        super().__init__(*args, **kwargs)
        self.subscribed_event_types: Set[str] = set()
        self.filters = {}
        self.event_bus = None  # Lazy initialization
        self.redis_subscriber = None

    def _get_event_bus(self):
        """Get event bus instance (lazy initialization)."""
        if self.event_bus is None:
            self.event_bus = get_event_bus()
        return self.event_bus

    async def connect(self):
        """Handle WebSocket connection."""
        # Check authentication
        user = self.scope.get("user")
        if isinstance(user, AnonymousUser) or not user:
            # Accept connection first (required by WebsocketCommunicator), then close
            await self.accept()
            await self.close(code=4001)  # Unauthorized
            return

        # Get tenant
        tenant = self.scope.get("tenant")
        if not tenant:
            # Accept connection first (required by WebsocketCommunicator), then close
            await self.accept()
            await self.send_error("User must belong to a tenant")
            await self.close(code=4003)  # Forbidden
            return

        # Accept connection
        await self.accept()

        # Send connection confirmation
        await self.send_json_message(
            WebSocketMessage(
                type=WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value,
                data={"message": "Connected to event stream"},
            )
        )

        logger.info(
            "websocket_connected",
            user_id=str(user.id),
            tenant_id=str(tenant.id),
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Unsubscribe from event bus
        if self.redis_subscriber:
            await self._unsubscribe_from_events()

        logger.info(
            "websocket_disconnected",
            close_code=close_code,
            user_id=str(self.scope.get("user").id) if self.scope.get("user") else None,
        )

    async def receive(self, text_data=None, bytes_data=None):
        """Handle incoming WebSocket message."""
        # Handle both text and binary data
        if bytes_data:
            try:
                text_data = bytes_data.decode('utf-8')
            except UnicodeDecodeError:
                await self.send_error("Invalid message encoding")
                return
        
        if not text_data:
            await self.send_error("Empty message")
            return
        
        try:
            # Handle both JSON strings and already-parsed dicts
            if isinstance(text_data, str):
                # Try to parse as JSON string
                try:
                    message = WebSocketMessage.from_json(text_data)
                except json.JSONDecodeError:
                    await self.send_error("Invalid JSON message")
                    return
            elif isinstance(text_data, dict):
                # Already parsed, create message directly
                message = WebSocketMessage(**text_data)
            else:
                await self.send_error("Invalid message format")
                return
        except Exception as e:
            logger.error("websocket_message_parse_error", error=str(e))
            await self.send_error("Failed to parse message")
            return

        # Handle message based on type
        if message.type == WebSocketMessageType.SUBSCRIBE.value:
            await self.handle_subscribe(message)
        elif message.type == WebSocketMessageType.UNSUBSCRIBE.value:
            await self.handle_unsubscribe(message)
        elif message.type == WebSocketMessageType.PING.value:
            await self.handle_ping(message)
        else:
            await self.send_error(f"Unknown message type: {message.type}")

    async def handle_subscribe(self, message: WebSocketMessage):
        """Handle subscribe message."""
        try:
            subscribe_msg = SubscribeMessage.from_dict(message.data or {})
        except Exception as e:
            logger.error("websocket_subscribe_parse_error", error=str(e))
            await self.send_error("Invalid subscribe message format")
            return

        # Validate event types
        if not subscribe_msg.event_types:
            await self.send_error("No event types specified")
            return

        # Subscribe to events
        self.subscribed_event_types.update(subscribe_msg.event_types)
        self.filters = subscribe_msg.filters or {}

        # Subscribe to event bus
        await self._subscribe_to_events()

        # Send confirmation
        await self.send_json_message(
            WebSocketMessage(
                type=WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value,
                data={
                    "event_types": list(self.subscribed_event_types),
                    "filters": self.filters,
                },
            )
        )

        logger.info(
            "websocket_subscribed",
            event_types=list(self.subscribed_event_types),
            user_id=str(self.scope.get("user").id),
        )

    async def handle_unsubscribe(self, message: WebSocketMessage):
        """Handle unsubscribe message."""
        event_types = message.data.get("event_types", []) if message.data else []

        if event_types:
            # Unsubscribe from specific event types
            self.subscribed_event_types.difference_update(event_types)
        else:
            # Unsubscribe from all
            self.subscribed_event_types.clear()

        # Update subscription
        if self.subscribed_event_types:
            await self._subscribe_to_events()
        else:
            await self._unsubscribe_from_events()

        logger.info(
            "websocket_unsubscribed",
            event_types=event_types,
            remaining_subscriptions=list(self.subscribed_event_types),
        )

    async def handle_ping(self, message: WebSocketMessage):
        """Handle ping message."""
        await self.send_json_message(
            WebSocketMessage(
                type=WebSocketMessageType.PONG.value,
                data={"timestamp": message.timestamp},
            )
        )

    async def _subscribe_to_events(self):
        """Subscribe to event bus for subscribed event types."""
        # Lazy initialize event bus to avoid database access during __init__
        try:
            event_bus = self._get_event_bus()
            # This would integrate with the event bus to receive events
            # For now, we'll set up a basic subscription mechanism
            # In production, this would use Redis Pub/Sub or similar
        except Exception as e:
            logger.warning("websocket_event_bus_subscribe_failed", error=str(e))

    async def _unsubscribe_from_events(self):
        """Unsubscribe from event bus."""
        if self.redis_subscriber:
            # Close Redis subscription
            self.redis_subscriber = None

    async def send_event(self, event: dict):
        """Send event to WebSocket client."""
        try:
            event_msg = EventMessage.from_dict(event)
            await self.send_json_message(
                WebSocketMessage(
                    type=WebSocketMessageType.EVENT.value,
                    data=event_msg.to_dict(),
                )
            )
        except Exception as e:
            logger.error("websocket_send_event_error", error=str(e))

    async def send_error(self, error_message: str, request_id: str = None):
        """Send error message to WebSocket client."""
        await self.send_json_message(
            WebSocketMessage(
                type=WebSocketMessageType.ERROR.value,
                error=error_message,
                request_id=request_id,
            )
        )

    async def send_json_message(self, message: WebSocketMessage):
        """Send JSON message to WebSocket client."""
        await self.send(text_data=message.to_json())

