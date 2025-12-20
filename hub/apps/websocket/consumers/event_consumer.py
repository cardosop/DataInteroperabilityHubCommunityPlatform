"""
Event Consumer

WebSocket consumer for real-time event updates.
"""
import json
import asyncio
from typing import Set, Optional
from datetime import datetime, timedelta
from django.conf import settings

import structlog
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from hub.apps.core.events.bus import get_event_bus
from hub.apps.core.events.deduplication import (
    generate_deduplication_key,
    check_event_duplicate,
    store_event_id,
    get_redis_client as get_deduplication_redis_client,
)
from hub.apps.websocket.protocol import (
    EventMessage,
    SubscribeMessage,
    WebSocketMessage,
    WebSocketMessageType,
)

logger = structlog.get_logger(__name__)

# Default configuration values
DEFAULT_PING_INTERVAL = 30  # seconds
DEFAULT_PONG_TIMEOUT = 10  # seconds
DEFAULT_CONNECTION_TIMEOUT = 300  # seconds (5 minutes)


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
        self.deduplication_redis_client = None  # Lazy initialization for deduplication

        # Connection health tracking
        self.last_activity: Optional[datetime] = None
        self.last_pong_received: Optional[datetime] = None
        self.pending_ping: bool = False
        self.ping_task: Optional[asyncio.Task] = None
        self.health_check_task: Optional[asyncio.Task] = None
        self._connection_closed = False

        # Configuration from settings
        self.ping_interval = getattr(settings, 'WEBSOCKET_PING_INTERVAL', DEFAULT_PING_INTERVAL)
        self.pong_timeout = getattr(settings, 'WEBSOCKET_PONG_TIMEOUT', DEFAULT_PONG_TIMEOUT)
        self.connection_timeout = getattr(settings, 'WEBSOCKET_CONNECTION_TIMEOUT', DEFAULT_CONNECTION_TIMEOUT)

    def _get_event_bus(self):
        """Get event bus instance (lazy initialization)."""
        if self.event_bus is None:
            self.event_bus = get_event_bus()
        return self.event_bus

    def _get_deduplication_redis_client(self):
        """Get Redis client for deduplication (lazy initialization)."""
        if self.deduplication_redis_client is None:
            self.deduplication_redis_client = get_deduplication_redis_client()
        return self.deduplication_redis_client

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

        # Initialize connection health tracking
        self.last_activity = datetime.utcnow()
        self.last_pong_received = datetime.utcnow()
        self._connection_closed = False

        # Send connection confirmation
        await self.send_json_message(
            WebSocketMessage(
                type=WebSocketMessageType.SUBSCRIPTION_CONFIRMED.value,
                data={"message": "Connected to event stream"},
            )
        )

        # Start background tasks for connection health monitoring
        self.ping_task = asyncio.create_task(self._ping_loop())
        self.health_check_task = asyncio.create_task(self._health_check_loop())

        logger.info(
            "websocket_connected",
            user_id=str(user.id),
            tenant_id=str(tenant.id),
            ping_interval=self.ping_interval,
            connection_timeout=self.connection_timeout,
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Mark connection as closed
        self._connection_closed = True

        # Cancel background tasks
        if self.ping_task and not self.ping_task.done():
            self.ping_task.cancel()
            try:
                await self.ping_task
            except asyncio.CancelledError:
                pass

        if self.health_check_task and not self.health_check_task.done():
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass

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

        # Update last activity timestamp
        self.last_activity = datetime.utcnow()

        # Handle message based on type
        if message.type == WebSocketMessageType.SUBSCRIBE.value:
            await self.handle_subscribe(message)
        elif message.type == WebSocketMessageType.UNSUBSCRIBE.value:
            await self.handle_unsubscribe(message)
        elif message.type == WebSocketMessageType.LIST_SUBSCRIPTIONS.value:
            await self.handle_list_subscriptions(message)
        elif message.type == WebSocketMessageType.PING.value:
            await self.handle_ping(message)
        elif message.type == WebSocketMessageType.PONG.value:
            await self.handle_pong(message)
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
            "websocket_unsubscribed",
            event_types=event_types,
            remaining_subscriptions=list(self.subscribed_event_types),
        )

    async def handle_list_subscriptions(self, message: WebSocketMessage):
        """Handle list subscriptions message."""
        # Get current subscriptions and filters
        subscriptions_data = {
            "event_types": list(self.subscribed_event_types),
            "filters": self.filters,
            "count": len(self.subscribed_event_types),
        }

        # Send subscriptions list
        await self.send_json_message(
            WebSocketMessage(
                type=WebSocketMessageType.SUBSCRIPTIONS_LIST.value,
                data=subscriptions_data,
                request_id=message.request_id,
            )
        )

        logger.debug(
            "websocket_subscriptions_listed",
            event_types=list(self.subscribed_event_types),
            count=len(self.subscribed_event_types),
            user_id=str(self.scope.get("user").id) if self.scope.get("user") else None,
        )

    async def handle_ping(self, message: WebSocketMessage):
        """Handle ping message from client."""
        # Update last activity
        self.last_activity = datetime.utcnow()

        # Send pong response
        await self.send_json_message(
            WebSocketMessage(
                type=WebSocketMessageType.PONG.value,
                data={"timestamp": message.timestamp},
            )
        )

    async def handle_pong(self, message: WebSocketMessage):
        """Handle pong message from client (response to server ping)."""
        # Update last activity and pong received timestamp
        self.last_activity = datetime.utcnow()
        self.last_pong_received = datetime.utcnow()
        self.pending_ping = False

        logger.debug(
            "websocket_pong_received",
            user_id=str(self.scope.get("user").id) if self.scope.get("user") else None,
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
        """Send event to WebSocket client with deduplication and filtering."""
        try:
            # Extract event type and data for deduplication
            event_type = event.get("event_type", "unknown")
            event_data = event.get("data", {})
            event_id = event.get("event_id")
            event_source = event.get("source", {})

            # Check if client is subscribed to this event type
            if not self._is_event_type_subscribed(event_type):
                logger.debug(
                    "websocket_event_not_subscribed",
                    event_id=event_id,
                    event_type=event_type,
                    subscribed_types=list(self.subscribed_event_types),
                )
                return  # Skip events not subscribed to

            # Apply tenant/resource filtering
            if not self._should_send_event(event, event_source):
                logger.debug(
                    "websocket_event_filtered_out",
                    event_id=event_id,
                    event_type=event_type,
                    filters=self.filters,
                )
                return  # Skip events that don't match filters

            # Check deduplication before sending
            if event_id and event_type != "unknown":
                deduplication_key = generate_deduplication_key(event_type, event_data)
                redis_client = self._get_deduplication_redis_client()

                if redis_client:
                    is_duplicate, existing_event_id = check_event_duplicate(
                        deduplication_key,
                        redis_client=redis_client
                    )

                    if is_duplicate:
                        # Event already processed - skip sending
                        logger.debug(
                            "websocket_event_duplicate_skipped",
                            event_id=event_id,
                            event_type=event_type,
                            existing_event_id=existing_event_id,
                            message=f"Event {event_id} already processed, skipping WebSocket delivery"
                        )
                        return  # Skip sending duplicate event

            # Send event to WebSocket client
            event_msg = EventMessage.from_dict(event)
            await self.send_json_message(
                WebSocketMessage(
                    type=WebSocketMessageType.EVENT.value,
                    data=event_msg.to_dict(),
                )
            )

            # Store event ID after successful send for deduplication
            if event_id and event_type != "unknown":
                redis_client = self._get_deduplication_redis_client()
                if redis_client:
                    deduplication_key = generate_deduplication_key(event_type, event_data)
                    store_event_id(
                        deduplication_key,
                        event_id,
                        redis_client=redis_client
                    )
        except Exception as e:
            logger.error("websocket_send_event_error", error=str(e))

    def _is_event_type_subscribed(self, event_type: str) -> bool:
        """
        Check if event type matches any subscribed event type pattern.

        Supports wildcard patterns (e.g., 'contract.*' matches 'contract.created').

        Args:
            event_type: Event type to check

        Returns:
            True if event type matches subscription, False otherwise
        """
        if not self.subscribed_event_types:
            return False

        for subscribed_type in self.subscribed_event_types:
            # Exact match
            if subscribed_type == event_type:
                return True

            # Wildcard pattern matching (e.g., 'contract.*' matches 'contract.created')
            if subscribed_type.endswith('.*'):
                prefix = subscribed_type[:-2]  # Remove '.*'
                if event_type.startswith(prefix + '.'):
                    return True

        return False

    def _should_send_event(self, event: dict, event_source: dict) -> bool:
        """
        Check if event should be sent based on filters.

        Filters can include:
        - tenant_id: Filter by tenant ID
        - resource_type: Filter by resource type
        - resource_id: Filter by specific resource ID
        - user_id: Filter by user ID

        Args:
            event: Event dictionary
            event_source: Event source dictionary

        Returns:
            True if event should be sent, False if filtered out
        """
        if not self.filters:
            return True  # No filters, send all subscribed events

        # Get current tenant from scope
        current_tenant = self.scope.get("tenant")
        current_user = self.scope.get("user")

        # Filter by tenant_id
        if "tenant_id" in self.filters:
            filter_tenant_id = str(self.filters["tenant_id"])
            event_tenant_id = str(event_source.get("tenant_id", ""))

            # If filter specifies tenant_id, event source tenant_id must match filter
            if filter_tenant_id:
                # If event has tenant_id, it must match filter
                if event_tenant_id and event_tenant_id != filter_tenant_id:
                    return False
                # If event doesn't have tenant_id, check if current tenant matches filter
                elif not event_tenant_id:
                    if not current_tenant or str(current_tenant.id) != filter_tenant_id:
                        return False

        # Filter by resource_type
        if "resource_type" in self.filters:
            filter_resource_type = self.filters["resource_type"]
            event_resource_type = event.get("data", {}).get("resource_type")

            if filter_resource_type and event_resource_type != filter_resource_type:
                return False

        # Filter by resource_id
        if "resource_id" in self.filters:
            filter_resource_id = str(self.filters["resource_id"])
            # Check multiple possible field names for resource ID
            event_data = event.get("data", {})
            event_resource_id = (
                str(event_data.get("resource_id", "")) or
                str(event_data.get("contract_id", "")) or
                str(event_data.get("asset_id", "")) or
                str(event_data.get("id", ""))
            )

            if filter_resource_id and event_resource_id != filter_resource_id:
                return False

        # Filter by user_id
        if "user_id" in self.filters:
            filter_user_id = str(self.filters["user_id"])
            event_user_id = str(event_source.get("user_id", ""))

            if filter_user_id:
                # If event has user_id, it must match filter
                if event_user_id and event_user_id != filter_user_id:
                    return False
                # If event doesn't have user_id, check if current user matches filter
                elif not event_user_id:
                    if not current_user or str(current_user.id) != filter_user_id:
                        return False

        # Filter by event_type (additional check beyond subscription)
        if "event_type" in self.filters:
            filter_event_type = self.filters["event_type"]
            event_type = event.get("event_type", "")

            if filter_event_type and event_type != filter_event_type:
                return False

        return True

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
        # Update last activity when sending messages
        self.last_activity = datetime.utcnow()
        await self.send(text_data=message.to_json())

    async def _ping_loop(self):
        """
        Background task to send periodic ping messages to client.

        Sends ping messages at configured intervals to keep connection alive
        and detect stale connections.
        """
        try:
            while not self._connection_closed:
                await asyncio.sleep(self.ping_interval)

                if self._connection_closed:
                    break

                # Check if connection is still active
                if self.last_activity and (datetime.utcnow() - self.last_activity).total_seconds() > self.connection_timeout:
                    logger.warning(
                        "websocket_connection_timeout",
                        user_id=str(self.scope.get("user").id) if self.scope.get("user") else None,
                        last_activity=self.last_activity.isoformat() if self.last_activity else None,
                        timeout_seconds=self.connection_timeout,
                    )
                    await self.close(code=4000)  # Normal closure due to timeout
                    break

                # Send ping if no pending ping
                if not self.pending_ping:
                    try:
                        ping_message = WebSocketMessage(
                            type=WebSocketMessageType.PING.value,
                            data={"timestamp": datetime.utcnow().isoformat()},
                        )
                        await self.send_json_message(ping_message)
                        self.pending_ping = True

                        logger.debug(
                            "websocket_ping_sent",
                            user_id=str(self.scope.get("user").id) if self.scope.get("user") else None,
                        )
                    except Exception as e:
                        logger.error(
                            "websocket_ping_error",
                            error=str(e),
                            user_id=str(self.scope.get("user").id) if self.scope.get("user") else None,
                            exc_info=True,
                        )
                        # Connection likely closed, break loop
                        break
        except asyncio.CancelledError:
            logger.debug("websocket_ping_loop_cancelled")
        except Exception as e:
            logger.error(
                "websocket_ping_loop_error",
                error=str(e),
                exc_info=True,
            )

    async def _health_check_loop(self):
        """
        Background task to check connection health and cleanup stale connections.

        Monitors:
        - Pending ping responses (pong timeout)
        - Overall connection timeout
        - Automatic cleanup of stale connections
        """
        try:
            while not self._connection_closed:
                await asyncio.sleep(self.pong_timeout)

                if self._connection_closed:
                    break

                # Check for pong timeout
                if self.pending_ping and self.last_pong_received:
                    time_since_pong = (datetime.utcnow() - self.last_pong_received).total_seconds()
                    if time_since_pong > self.pong_timeout:
                        logger.warning(
                            "websocket_pong_timeout",
                            user_id=str(self.scope.get("user").id) if self.scope.get("user") else None,
                            time_since_pong=time_since_pong,
                            pong_timeout=self.pong_timeout,
                        )
                        await self.close(code=4000)  # Normal closure due to pong timeout
                        break

                # Check overall connection timeout
                if self.last_activity:
                    time_since_activity = (datetime.utcnow() - self.last_activity).total_seconds()
                    if time_since_activity > self.connection_timeout:
                        logger.warning(
                            "websocket_connection_inactive_timeout",
                            user_id=str(self.scope.get("user").id) if self.scope.get("user") else None,
                            time_since_activity=time_since_activity,
                            connection_timeout=self.connection_timeout,
                        )
                        await self.close(code=4000)  # Normal closure due to inactivity
                        break
        except asyncio.CancelledError:
            logger.debug("websocket_health_check_loop_cancelled")
        except Exception as e:
            logger.error(
                "websocket_health_check_loop_error",
                error=str(e),
                exc_info=True,
            )

