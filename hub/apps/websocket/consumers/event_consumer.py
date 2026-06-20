"""
Event Consumer

WebSocket consumer for real-time event updates.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import structlog
from django.conf import settings

try:
    from channels.generic.websocket import AsyncWebsocketConsumer

    CHANNELS_AVAILABLE = True
except ImportError:
    # Django Channels not available - create a proper stub that can be inherited
    class AsyncWebsocketConsumer:
        """Stub for AsyncWebsocketConsumer when channels is not available."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Django Channels is not installed. "
                "Install it with: pip install channels channels-redis"
            )

    CHANNELS_AVAILABLE = False
import contextlib

from django.contrib.auth.models import AnonymousUser

from hub.apps.core.events.bus import get_event_bus
from hub.apps.core.events.deduplication import (
    check_event_duplicate,
    generate_deduplication_key,
    store_event_id,
)
from hub.apps.core.events.deduplication import (
    get_redis_client as get_deduplication_redis_client,
)
from hub.apps.websocket.middleware.auth import get_user_from_token
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
DEFAULT_AUTH_TIMEOUT = 10  # seconds — disconnect if no authenticate message


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
        self.subscribed_event_types: set[str] = set()
        self.filters = {}
        self.event_bus = None  # Lazy initialization
        self.redis_subscriber = None
        self.deduplication_redis_client = None  # Lazy initialization for deduplication

        # Message-based authentication state
        self._awaiting_auth: bool = False
        self._auth_timeout_task: asyncio.Task | None = None

        # Connection health tracking
        self.last_activity: datetime | None = None
        self.last_pong_received: datetime | None = None
        self.pending_ping: bool = False
        self.ping_task: asyncio.Task | None = None
        self.health_check_task: asyncio.Task | None = None
        self._connection_closed = False

        # Event replay tracking - track last event timestamp per event type for replay on reconnection
        self.last_event_timestamps: dict[str, datetime] = {}  # event_type -> last timestamp
        self.replay_enabled = getattr(settings, "WEBSOCKET_EVENT_REPLAY_ENABLED", True)
        self.replay_window_seconds = getattr(
            settings, "WEBSOCKET_EVENT_REPLAY_WINDOW_SECONDS", 3600
        )  # 1 hour default

        # Configuration from settings
        self.ping_interval = getattr(settings, "WEBSOCKET_PING_INTERVAL", DEFAULT_PING_INTERVAL)
        self.pong_timeout = getattr(settings, "WEBSOCKET_PONG_TIMEOUT", DEFAULT_PONG_TIMEOUT)
        self.connection_timeout = getattr(
            settings, "WEBSOCKET_CONNECTION_TIMEOUT", DEFAULT_CONNECTION_TIMEOUT
        )
        self.auth_timeout = getattr(settings, "WEBSOCKET_AUTH_TIMEOUT", DEFAULT_AUTH_TIMEOUT)

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
        """Handle WebSocket connection.

        Supports two authentication paths:
        1. Pre-authenticated (middleware set scope["user"]): immediately ready.
        2. Pending message auth (scope["auth_method"] == "pending_message_auth"):
           accept the connection, start a timeout, and wait for an
           ``authenticate`` message before allowing any other operations.
        """
        auth_method = self.scope.get("auth_method")
        user = self.scope.get("user")

        # --- Pending message-based auth ---
        if auth_method == "pending_message_auth":
            # Accept connection and wait for authenticate message
            await self.accept()
            self._awaiting_auth = True
            self._connection_closed = False
            self.last_activity = datetime.now(UTC)

            # Start auth timeout — disconnect if no authenticate message
            self._auth_timeout_task = asyncio.create_task(self._auth_timeout_loop())

            logger.info(
                "websocket_awaiting_auth",
                path=self.scope.get("path"),
                auth_timeout=self.auth_timeout,
            )
            return

        # --- Pre-authenticated (from middleware: header or deprecated query param) ---
        if isinstance(user, AnonymousUser) or not user:
            await self.accept()
            await self.close(code=4001)  # Unauthorized
            return

        tenant = self.scope.get("tenant")
        if not tenant:
            await self.accept()
            await self.send_error("User must belong to a tenant")
            await self.close(code=4003)  # Forbidden
            return

        # Accept connection
        await self.accept()
        await self._complete_authenticated_setup(user, tenant)

    async def _complete_authenticated_setup(
        self,
        user,
        tenant,
        *,
        send_confirmation=True,
    ):
        """Shared setup after authentication (both middleware and message-based).

        Args:
            user: Authenticated user.
            tenant: User's tenant.
            send_confirmation: Whether to send the ``subscription_confirmed``
                connection message.  Set to ``False`` for message-based auth
                where ``auth_confirmed`` was already sent.
        """
        # Initialize connection health tracking
        self.last_activity = datetime.now(UTC)
        self.last_pong_received = datetime.now(UTC)
        self._connection_closed = False

        if send_confirmation:
            # Send connection confirmation (pre-authenticated path only;
            # message-based auth already sent AUTH_CONFIRMED).
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

        # Cancel auth timeout task
        if self._auth_timeout_task and not self._auth_timeout_task.done():
            self._auth_timeout_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._auth_timeout_task

        # Cancel background tasks
        if self.ping_task and not self.ping_task.done():
            self.ping_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.ping_task

        if self.health_check_task and not self.health_check_task.done():
            self.health_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.health_check_task

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
                text_data = bytes_data.decode("utf-8")
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
        self.last_activity = datetime.now(UTC)

        # --- Gate: authenticate message when awaiting auth ---
        if message.type == WebSocketMessageType.AUTHENTICATE.value:
            await self.handle_authenticate(message)
            return

        # --- Gate: reject all other messages before authentication ---
        if self._awaiting_auth:
            await self.send_error("Authentication required. Send an 'authenticate' message first.")
            return

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

    async def handle_authenticate(self, message: WebSocketMessage):
        """Handle message-based authentication.

        Expects: ``{ "type": "authenticate", "data": { "token": "<jwt>" } }``
        """
        # Reject if already authenticated
        if not self._awaiting_auth:
            await self.send_error("Already authenticated")
            return

        data = message.data or {}
        token = data.get("token")
        if not token:
            await self.send_error("Missing token field in authenticate message")
            await self.close(code=4001)
            return

        user = await get_user_from_token(token)
        if not user:
            await self.send_error("Authentication failed: invalid token")
            await self.close(code=4001)
            return

        tenant = user.tenant if hasattr(user, "tenant") else None
        if not tenant:
            await self.send_error("User must belong to a tenant")
            await self.close(code=4003)
            return

        # Authentication successful — cancel timeout, set scope, transition
        self._awaiting_auth = False
        if self._auth_timeout_task and not self._auth_timeout_task.done():
            self._auth_timeout_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._auth_timeout_task

        self.scope["user"] = user
        self.scope["tenant"] = tenant
        self.scope["auth_method"] = "message_auth"

        # Send auth confirmation
        await self.send_json_message(
            WebSocketMessage(
                type=WebSocketMessageType.AUTH_CONFIRMED.value,
                data={
                    "message": "Authenticated successfully",
                    "user_id": str(user.id),
                },
            )
        )

        # Complete the standard authenticated setup (ping/pong, health check).
        # send_confirmation=False because AUTH_CONFIRMED was already sent above.
        await self._complete_authenticated_setup(
            user,
            tenant,
            send_confirmation=False,
        )

        logger.info(
            "websocket_message_auth_success",
            user_id=str(user.id),
            tenant_id=str(tenant.id),
        )

    async def _auth_timeout_loop(self):
        """Close connection if no authenticate message within the timeout."""
        try:
            await asyncio.sleep(self.auth_timeout)
            if self._awaiting_auth and not self._connection_closed:
                logger.warning(
                    "websocket_auth_timeout",
                    auth_timeout=self.auth_timeout,
                    path=self.scope.get("path"),
                )
                await self.send_error("Authentication timeout: no authenticate message received")
                await self.close(code=4001)
        except asyncio.CancelledError:
            pass

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

        # Replay missed events on subscription (if replay is enabled)
        if self.replay_enabled:
            await self._replay_missed_odps_events()
            await self._replay_missed_mesh_events()
            await self._replay_missed_virtualization_events()

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
        self.last_activity = datetime.now(UTC)

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
        self.last_activity = datetime.now(UTC)
        self.last_pong_received = datetime.now(UTC)
        self.pending_ping = False

        logger.debug(
            "websocket_pong_received",
            user_id=str(self.scope.get("user").id) if self.scope.get("user") else None,
        )

    async def _subscribe_to_events(self):
        """Subscribe to event bus for subscribed event types."""
        # Lazy initialize event bus to avoid database access during __init__
        try:
            self._get_event_bus()
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

    async def _replay_missed_odps_events(self):
        """
        Replay missed ODPS events on reconnection.

        Queries the database for ODPS events that occurred since the last connection
        and replays them to the client. This ensures clients don't miss events during
        disconnections.
        """
        try:
            # Get tenant for filtering
            tenant = self.scope.get("tenant")
            if not tenant:
                return  # Can't replay without tenant context

            # Get subscribed ODPS event types
            odps_event_types = [
                event_type
                for event_type in self.subscribed_event_types
                if event_type.startswith("odps.") or event_type == "odps.*"
            ]

            if not odps_event_types:
                return  # No ODPS events subscribed

            # Calculate replay window
            replay_start_time = None
            if self.last_event_timestamps:
                # Use the most recent timestamp across all ODPS event types
                odps_timestamps = [
                    ts
                    for event_type, ts in self.last_event_timestamps.items()
                    if event_type.startswith("odps.")
                ]
                if odps_timestamps:
                    replay_start_time = max(odps_timestamps)
            else:
                # No previous events - use replay window
                replay_start_time = datetime.now(UTC) - timedelta(
                    seconds=self.replay_window_seconds
                )

            # Replay events for each subscribed ODPS event type
            event_bus = self._get_event_bus()
            replayed_count = 0

            for event_type_pattern in odps_event_types:
                # Determine actual event types to query
                if event_type_pattern == "odps.*":
                    # Query all ODPS events
                    pass  # None means all ODPS events
                elif event_type_pattern.endswith(".*"):
                    # Pattern like "odps.workflow.*" - query events matching the prefix
                    prefix = event_type_pattern[:-2]  # Remove '.*'
                    # Query events that start with this prefix
                else:
                    # Exact event type
                    pass

                # Query events from database
                try:
                    # Use event bus replay_events method
                    # For patterns, we need to query ODPS events and filter
                    # Query events from database based on pattern type
                    # Use sync_to_async for database queries in async context
                    from asgiref.sync import sync_to_async

                    from hub.apps.core.events.models import Event as EventModel

                    if event_type_pattern == "odps.*":
                        # Query all ODPS events - use a query that gets all ODPS event types
                        # Query all ODPS events from database
                        def _query_odps_events():
                            return list(
                                EventModel.objects.filter(
                                    event_type__startswith="odps.",
                                    tenant_id=tenant.id,
                                    timestamp__gte=replay_start_time,
                                ).order_by("timestamp")[:1000]
                            )

                        odps_events_list = await sync_to_async(_query_odps_events)()

                        # Convert to event dictionaries
                        events_to_replay = []
                        for event_obj in odps_events_list:
                            event_dict = {
                                "event_id": str(event_obj.event_id),
                                "event_type": event_obj.event_type,
                                "event_version": event_obj.event_version,
                                "timestamp": event_obj.timestamp.isoformat() + "Z",
                                "source": {
                                    "service": event_obj.source_service,
                                    "tenant_id": str(event_obj.tenant_id)
                                    if event_obj.tenant_id
                                    else None,
                                },
                                "data": event_obj.data,
                                "metadata": event_obj.metadata or {},
                            }
                            if event_obj.user_id:
                                event_dict["source"]["user_id"] = str(event_obj.user_id)
                            if event_obj.request_id:
                                event_dict["source"]["request_id"] = event_obj.request_id
                            events_to_replay.append(event_dict)
                    elif event_type_pattern.endswith(".*"):
                        # Pattern like "odps.workflow.*" - query events matching the prefix
                        prefix = event_type_pattern[:-2]  # Remove '.*'

                        def _query_pattern_events():
                            return list(
                                EventModel.objects.filter(
                                    event_type__startswith=prefix + ".",
                                    tenant_id=tenant.id,
                                    timestamp__gte=replay_start_time,
                                ).order_by("timestamp")[:1000]
                            )

                        pattern_events_list = await sync_to_async(_query_pattern_events)()

                        # Convert to event dictionaries
                        events_to_replay = []
                        for event_obj in pattern_events_list:
                            event_dict = {
                                "event_id": str(event_obj.event_id),
                                "event_type": event_obj.event_type,
                                "event_version": event_obj.event_version,
                                "timestamp": event_obj.timestamp.isoformat() + "Z",
                                "source": {
                                    "service": event_obj.source_service,
                                    "tenant_id": str(event_obj.tenant_id)
                                    if event_obj.tenant_id
                                    else None,
                                },
                                "data": event_obj.data,
                                "metadata": event_obj.metadata or {},
                            }
                            if event_obj.user_id:
                                event_dict["source"]["user_id"] = str(event_obj.user_id)
                            if event_obj.request_id:
                                event_dict["source"]["request_id"] = event_obj.request_id
                            events_to_replay.append(event_dict)
                    else:
                        # Exact event type - use sync_to_async for replay_events
                        events_to_replay = await sync_to_async(event_bus.replay_events)(
                            event_type=event_type_pattern,
                            tenant_id=str(tenant.id),
                            start_time=replay_start_time,
                            limit=1000,
                        )

                    # Apply filters and send events
                    for event in events_to_replay:
                        event_source = event.get("source", {})
                        # Apply the same filtering logic as real-time events
                        if self._should_send_event(event, event_source):
                            # Check deduplication before replaying
                            event_id = event.get("event_id")
                            event_type = event.get("event_type", "unknown")
                            event_data = event.get("data", {})

                            if event_id and event_type != "unknown":
                                redis_client = self._get_deduplication_redis_client()
                                if redis_client:
                                    deduplication_key = generate_deduplication_key(
                                        event_type, event_data
                                    )
                                    is_duplicate, _ = check_event_duplicate(
                                        deduplication_key, redis_client=redis_client
                                    )
                                    if is_duplicate:
                                        # Skip duplicate events during replay
                                        continue

                            # Send replayed event
                            await self.send_event(event)
                            replayed_count += 1

                except Exception as replay_error:
                    logger.warning(
                        "websocket_odps_event_replay_error",
                        event_type_pattern=event_type_pattern,
                        error=str(replay_error),
                        exc_info=True,
                    )
                    # Continue with other event types even if one fails

            if replayed_count > 0:
                logger.info(
                    "websocket_odps_events_replayed",
                    count=replayed_count,
                    event_types=list(odps_event_types),
                    tenant_id=str(tenant.id),
                    replay_start_time=replay_start_time.isoformat() if replay_start_time else None,
                )

        except Exception as e:
            # Log error but don't fail subscription if replay fails
            logger.error("websocket_odps_event_replay_failed", error=str(e), exc_info=True)

    async def _replay_missed_mesh_events(self):
        """
        Replay missed mesh events on reconnection.

        Queries the database for mesh events that occurred since the last connection
        and replays them to the client. This ensures clients don't miss events during
        disconnections.
        """
        try:
            # Get tenant for filtering
            tenant = self.scope.get("tenant")
            if not tenant:
                return  # Can't replay without tenant context

            # Get subscribed mesh event types
            mesh_event_types = [
                event_type
                for event_type in self.subscribed_event_types
                if event_type.startswith("mesh.") or event_type == "mesh.*"
            ]

            if not mesh_event_types:
                return  # No mesh events subscribed

            # Calculate replay window
            replay_start_time = None
            if self.last_event_timestamps:
                # Use the most recent timestamp across all mesh event types
                mesh_timestamps = [
                    ts
                    for event_type, ts in self.last_event_timestamps.items()
                    if event_type.startswith("mesh.")
                ]
                if mesh_timestamps:
                    replay_start_time = max(mesh_timestamps)
            else:
                # No previous events - use replay window
                replay_start_time = datetime.now(UTC) - timedelta(
                    seconds=self.replay_window_seconds
                )

            # Replay events for each subscribed mesh event type
            event_bus = self._get_event_bus()
            replayed_count = 0

            for event_type_pattern in mesh_event_types:
                # Determine actual event types to query
                if event_type_pattern == "mesh.*":
                    # Query all mesh events
                    pass  # None means all mesh events
                elif event_type_pattern.endswith(".*"):
                    # Pattern like "mesh.domain.*" - query events matching the prefix
                    prefix = event_type_pattern[:-2]  # Remove '.*'
                    # Query events that start with this prefix
                else:
                    # Exact event type
                    pass

                # Query events from database
                try:
                    # Use event bus replay_events method
                    from asgiref.sync import sync_to_async

                    from hub.apps.core.events.models import Event as EventModel

                    if event_type_pattern == "mesh.*":
                        # Query all mesh events
                        def _query_mesh_events():
                            return list(
                                EventModel.objects.filter(
                                    event_type__startswith="mesh.",
                                    tenant_id=tenant.id,
                                    timestamp__gte=replay_start_time,
                                ).order_by("timestamp")[:1000]
                            )

                        mesh_events_list = await sync_to_async(_query_mesh_events)()

                        # Convert to event dictionaries
                        events_to_replay = []
                        for event_obj in mesh_events_list:
                            event_dict = {
                                "event_id": str(event_obj.event_id),
                                "event_type": event_obj.event_type,
                                "event_version": event_obj.event_version,
                                "timestamp": event_obj.timestamp.isoformat() + "Z",
                                "source": {
                                    "service": event_obj.source_service,
                                    "tenant_id": str(event_obj.tenant_id)
                                    if event_obj.tenant_id
                                    else None,
                                },
                                "data": event_obj.data,
                                "metadata": event_obj.metadata or {},
                            }
                            if event_obj.user_id:
                                event_dict["source"]["user_id"] = str(event_obj.user_id)
                            if event_obj.request_id:
                                event_dict["source"]["request_id"] = event_obj.request_id
                            events_to_replay.append(event_dict)
                    elif event_type_pattern.endswith(".*"):
                        # Pattern like "mesh.domain.*" - query events matching the prefix
                        prefix = event_type_pattern[:-2]  # Remove '.*'

                        def _query_pattern_events():
                            return list(
                                EventModel.objects.filter(
                                    event_type__startswith=prefix + ".",
                                    tenant_id=tenant.id,
                                    timestamp__gte=replay_start_time,
                                ).order_by("timestamp")[:1000]
                            )

                        pattern_events_list = await sync_to_async(_query_pattern_events)()

                        # Convert to event dictionaries
                        events_to_replay = []
                        for event_obj in pattern_events_list:
                            event_dict = {
                                "event_id": str(event_obj.event_id),
                                "event_type": event_obj.event_type,
                                "event_version": event_obj.event_version,
                                "timestamp": event_obj.timestamp.isoformat() + "Z",
                                "source": {
                                    "service": event_obj.source_service,
                                    "tenant_id": str(event_obj.tenant_id)
                                    if event_obj.tenant_id
                                    else None,
                                },
                                "data": event_obj.data,
                                "metadata": event_obj.metadata or {},
                            }
                            if event_obj.user_id:
                                event_dict["source"]["user_id"] = str(event_obj.user_id)
                            if event_obj.request_id:
                                event_dict["source"]["request_id"] = event_obj.request_id
                            events_to_replay.append(event_dict)
                    else:
                        # Exact event type - use sync_to_async for replay_events
                        events_to_replay = await sync_to_async(event_bus.replay_events)(
                            event_type=event_type_pattern,
                            tenant_id=str(tenant.id),
                            start_time=replay_start_time,
                            limit=1000,
                        )

                    # Apply filters and send events
                    for event in events_to_replay:
                        # Check if event matches filters
                        if self._should_send_event(event, event.get("source", {})):
                            # Check deduplication for replayed events
                            event_id = event.get("event_id")
                            event_type = event.get("event_type")
                            event_data = event.get("data", {})

                            if event_id and event_type:
                                deduplication_key = generate_deduplication_key(
                                    event_type, event_data
                                )
                                redis_client = self._get_deduplication_redis_client()

                                if redis_client:
                                    is_duplicate, _existing_event_id = check_event_duplicate(
                                        deduplication_key, redis_client=redis_client
                                    )
                                    if is_duplicate:
                                        # Skip duplicate events during replay
                                        continue

                            # Send replayed event
                            await self.send_event(event)
                            replayed_count += 1

                except Exception as replay_error:
                    logger.warning(
                        "websocket_mesh_event_replay_error",
                        event_type_pattern=event_type_pattern,
                        error=str(replay_error),
                        exc_info=True,
                    )
                    # Continue with other event types even if one fails

            if replayed_count > 0:
                logger.info(
                    "websocket_mesh_events_replayed",
                    count=replayed_count,
                    event_types=list(mesh_event_types),
                    tenant_id=str(tenant.id),
                    replay_start_time=replay_start_time.isoformat() if replay_start_time else None,
                )

        except Exception as e:
            # Log error but don't fail subscription if replay fails
            logger.error("websocket_mesh_event_replay_failed", error=str(e), exc_info=True)

    async def _replay_missed_virtualization_events(self):
        """
        Replay missed virtualization events on reconnection.

        Queries the database for virtualization events that occurred since the last connection
        and replays them to the client. This ensures clients don't miss events during
        disconnections.
        """
        try:
            # Get tenant for filtering
            tenant = self.scope.get("tenant")
            if not tenant:
                return  # Can't replay without tenant context

            # Get subscribed virtualization event types
            virtualization_event_types = [
                event_type
                for event_type in self.subscribed_event_types
                if event_type.startswith("virtualization.") or event_type == "virtualization.*"
            ]

            if not virtualization_event_types:
                return  # No virtualization events subscribed

            # Calculate replay window
            replay_start_time = None
            if self.last_event_timestamps:
                # Use the most recent timestamp across all virtualization event types
                virtualization_timestamps = [
                    ts
                    for event_type, ts in self.last_event_timestamps.items()
                    if event_type.startswith("virtualization.")
                ]
                if virtualization_timestamps:
                    replay_start_time = max(virtualization_timestamps)
            else:
                # No previous events - use replay window
                replay_start_time = datetime.now(UTC) - timedelta(
                    seconds=self.replay_window_seconds
                )

            # Replay events for each subscribed virtualization event type
            event_bus = self._get_event_bus()
            replayed_count = 0

            for event_type_pattern in virtualization_event_types:
                # Determine actual event types to query
                if event_type_pattern == "virtualization.*":
                    # Query all virtualization events
                    pass  # None means all virtualization events
                elif event_type_pattern.endswith(".*"):
                    # Pattern like "virtualization.query.*" - query events matching the prefix
                    prefix = event_type_pattern[:-2]  # Remove '.*'
                    # Query events that start with this prefix
                else:
                    # Exact event type
                    pass

                # Query events from database
                try:
                    # Use event bus replay_events method
                    from asgiref.sync import sync_to_async

                    from hub.apps.core.events.models import Event as EventModel

                    if event_type_pattern == "virtualization.*":
                        # Query all virtualization events
                        def _query_virtualization_events():
                            return list(
                                EventModel.objects.filter(
                                    event_type__startswith="virtualization.",
                                    tenant_id=tenant.id,
                                    timestamp__gte=replay_start_time,
                                ).order_by("timestamp")[:1000]
                            )

                        virtualization_events_list = await sync_to_async(
                            _query_virtualization_events
                        )()

                        # Convert to event dictionaries
                        events_to_replay = []
                        for event_obj in virtualization_events_list:
                            event_dict = {
                                "event_id": str(event_obj.event_id),
                                "event_type": event_obj.event_type,
                                "event_version": event_obj.event_version,
                                "timestamp": event_obj.timestamp.isoformat() + "Z",
                                "source": {
                                    "service": event_obj.source_service,
                                    "tenant_id": str(event_obj.tenant_id)
                                    if event_obj.tenant_id
                                    else None,
                                },
                                "data": event_obj.data,
                                "metadata": event_obj.metadata or {},
                            }
                            if event_obj.user_id:
                                event_dict["source"]["user_id"] = str(event_obj.user_id)
                            if event_obj.request_id:
                                event_dict["source"]["request_id"] = event_obj.request_id
                            events_to_replay.append(event_dict)
                    elif event_type_pattern.endswith(".*"):
                        # Pattern like "virtualization.query.*" - query events matching the prefix
                        prefix = event_type_pattern[:-2]  # Remove '.*'

                        def _query_pattern_events():
                            return list(
                                EventModel.objects.filter(
                                    event_type__startswith=prefix + ".",
                                    tenant_id=tenant.id,
                                    timestamp__gte=replay_start_time,
                                ).order_by("timestamp")[:1000]
                            )

                        pattern_events_list = await sync_to_async(_query_pattern_events)()

                        # Convert to event dictionaries
                        events_to_replay = []
                        for event_obj in pattern_events_list:
                            event_dict = {
                                "event_id": str(event_obj.event_id),
                                "event_type": event_obj.event_type,
                                "event_version": event_obj.event_version,
                                "timestamp": event_obj.timestamp.isoformat() + "Z",
                                "source": {
                                    "service": event_obj.source_service,
                                    "tenant_id": str(event_obj.tenant_id)
                                    if event_obj.tenant_id
                                    else None,
                                },
                                "data": event_obj.data,
                                "metadata": event_obj.metadata or {},
                            }
                            if event_obj.user_id:
                                event_dict["source"]["user_id"] = str(event_obj.user_id)
                            if event_obj.request_id:
                                event_dict["source"]["request_id"] = event_obj.request_id
                            events_to_replay.append(event_dict)
                    else:
                        # Exact event type - use sync_to_async for replay_events
                        events_to_replay = await sync_to_async(event_bus.replay_events)(
                            event_type=event_type_pattern,
                            tenant_id=str(tenant.id),
                            start_time=replay_start_time,
                            limit=1000,
                        )

                    # Apply filters and send events
                    for event in events_to_replay:
                        # Check if event matches filters
                        if self._should_send_event(event, event.get("source", {})):
                            # Check deduplication for replayed events
                            event_id = event.get("event_id")
                            event_type = event.get("event_type")
                            event_data = event.get("data", {})

                            if event_id and event_type:
                                deduplication_key = generate_deduplication_key(
                                    event_type, event_data
                                )
                                redis_client = self._get_deduplication_redis_client()

                                if redis_client:
                                    is_duplicate, _existing_event_id = check_event_duplicate(
                                        deduplication_key, redis_client=redis_client
                                    )
                                    if is_duplicate:
                                        # Skip duplicate events during replay
                                        continue

                            # Send replayed event
                            await self.send_event(event)
                            replayed_count += 1

                except Exception as replay_error:
                    logger.warning(
                        "websocket_virtualization_event_replay_error",
                        event_type_pattern=event_type_pattern,
                        error=str(replay_error),
                        exc_info=True,
                    )
                    # Continue with other event types even if one fails

            if replayed_count > 0:
                logger.info(
                    "websocket_virtualization_events_replayed",
                    count=replayed_count,
                    event_types=list(virtualization_event_types),
                    tenant_id=str(tenant.id),
                    replay_start_time=replay_start_time.isoformat() if replay_start_time else None,
                )

        except Exception as e:
            # Log error but don't fail subscription if replay fails
            logger.error(
                "websocket_virtualization_event_replay_failed", error=str(e), exc_info=True
            )

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
                        deduplication_key, redis_client=redis_client
                    )

                    if is_duplicate:
                        # Event already processed - skip sending
                        logger.debug(
                            "websocket_event_duplicate_skipped",
                            event_id=event_id,
                            event_type=event_type,
                            existing_event_id=existing_event_id,
                            message=f"Event {event_id} already processed, skipping WebSocket delivery",
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
                    store_event_id(deduplication_key, event_id, redis_client=redis_client)

                # Track last event timestamp for replay (ODPS events, mesh events, virtualization events, and all events)
                # Update last timestamp for this event type
                try:
                    event_timestamp_str = event.get("timestamp")
                    if event_timestamp_str:
                        # Normalize ISO timestamp to a form fromisoformat can parse.
                        # Handles: "...Z", "...+00:00", "...+00:00Z" (double-suffix)
                        ts = event_timestamp_str
                        # Strip trailing Z that follows an existing offset (e.g. +00:00Z)
                        if ts.endswith("+00:00Z"):
                            ts = ts[:-1]  # remove trailing Z
                        elif ts.endswith("Z"):
                            ts = ts[:-1] + "+00:00"
                        try:
                            event_timestamp = datetime.fromisoformat(ts)
                            # If timezone-naive, assume UTC
                            if event_timestamp.tzinfo is None:
                                from django.utils import timezone as django_timezone

                                event_timestamp = django_timezone.make_aware(event_timestamp)
                        except (ValueError, AttributeError):
                            # Fallback: use django timezone parsing
                            from django.utils.dateparse import parse_datetime

                            event_timestamp = parse_datetime(event_timestamp_str)
                            if event_timestamp:
                                from django.utils import timezone as django_timezone

                                if django_timezone.is_naive(event_timestamp):
                                    event_timestamp = django_timezone.make_aware(event_timestamp)

                        if event_timestamp:
                            self.last_event_timestamps[event_type] = event_timestamp

                            # Track for wildcard patterns (e.g., 'odps.*' -> track all odps.* events)
                            if event_type.startswith("odps."):
                                self.last_event_timestamps["odps.*"] = event_timestamp
                                # Track for nested patterns (e.g., 'odps.workflow.*')
                                if event_type.startswith("odps.workflow."):
                                    self.last_event_timestamps["odps.workflow.*"] = event_timestamp

                            # Track for virtualization event patterns
                            if event_type.startswith("virtualization."):
                                self.last_event_timestamps["virtualization.*"] = event_timestamp
                                # Track for nested patterns
                                if event_type.startswith("virtualization.query."):
                                    self.last_event_timestamps["virtualization.query.*"] = (
                                        event_timestamp
                                    )
                                    if event_type.startswith("virtualization.query.execution."):
                                        self.last_event_timestamps[
                                            "virtualization.query.execution.*"
                                        ] = event_timestamp
                                elif event_type.startswith("virtualization.dataset."):
                                    self.last_event_timestamps["virtualization.dataset.*"] = (
                                        event_timestamp
                                    )
                except Exception as timestamp_error:
                    # Log but don't fail event delivery if timestamp tracking fails
                    logger.warning(
                        "websocket_event_timestamp_tracking_failed",
                        event_id=event_id,
                        event_type=event_type,
                        error=str(timestamp_error),
                    )
        except Exception as e:
            logger.error("websocket_send_event_error", error=str(e))

    def _is_event_type_subscribed(self, event_type: str) -> bool:
        """
        Check if event type matches any subscribed event type pattern.

        Supports wildcard patterns (e.g., 'contract.*' matches 'contract.created').
        Enhanced to support ODPS events and nested patterns (e.g., 'odps.workflow.*').

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
            if subscribed_type.endswith(".*"):
                prefix = subscribed_type[:-2]  # Remove '.*'
                if event_type.startswith(prefix + "."):
                    return True

            # ODPS-specific pattern matching
            # Support patterns like 'odps.*' matching all ODPS events
            # Support patterns like 'odps.workflow.*' matching workflow events
            if subscribed_type.startswith("odps.") and event_type.startswith("odps."):
                # Check if it's a nested pattern (e.g., 'odps.workflow.*')
                if "." in subscribed_type[5:]:  # After 'odps.'
                    # Nested pattern: 'odps.workflow.*'
                    pattern_parts = subscribed_type.split(".")
                    event_parts = event_type.split(".")
                    if len(pattern_parts) <= len(event_parts):
                        # Check if all pattern parts (except the last '*') match
                        match = True
                        for i, pattern_part in enumerate(pattern_parts[:-1]):  # Exclude last '*'
                            if i < len(event_parts) and pattern_part != event_parts[i]:
                                match = False
                                break
                        if match:
                            return True
                # Simple 'odps.*' pattern - matches all ODPS events
                elif subscribed_type == "odps.*" and event_type.startswith("odps."):
                    return True

            # Virtualization-specific pattern matching
            # Support patterns like 'virtualization.*' matching all virtualization events
            # Support patterns like 'virtualization.query.*' matching query events
            if subscribed_type.startswith("virtualization."):
                if event_type.startswith("virtualization."):
                    # Only apply wildcard matching if subscribed_type ends with '.*'
                    if subscribed_type.endswith(".*"):
                        # Check if it's a nested pattern (e.g., 'virtualization.query.*')
                        if "." in subscribed_type[16:-2]:  # After 'virtualization.' and before '.*'
                            # Nested pattern: 'virtualization.query.*'
                            pattern_parts = subscribed_type[:-2].split(
                                "."
                            )  # Remove '.*' before splitting
                            event_parts = event_type.split(".")
                            if len(pattern_parts) <= len(event_parts):
                                # Check if all pattern parts match
                                match = True
                                for i, pattern_part in enumerate(pattern_parts):
                                    if i < len(event_parts) and pattern_part != event_parts[i]:
                                        match = False
                                        break
                                if match:
                                    return True
                        # Simple 'virtualization.*' pattern - matches all virtualization events
                        elif subscribed_type == "virtualization.*" and event_type.startswith(
                            "virtualization."
                        ):
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
            event_type = event.get("event_type", "")

            # ODPS-specific resource ID fields
            if event_type.startswith("odps."):
                # For ODPS events, check all possible resource ID fields
                # The filter should match if ANY of these IDs match
                possible_resource_ids = [
                    str(event_data.get("resource_id", "")),
                    str(event_data.get("odps_contract_id", "")),
                    str(event_data.get("odcs_contract_id", "")),
                    str(event_data.get("contract_id", "")),
                    str(event_data.get("asset_id", "")),
                    str(event_data.get("id", "")),
                ]
                # Filter out empty strings
                possible_resource_ids = [
                    rid for rid in possible_resource_ids if rid and rid != "None"
                ]

                # Check if filter matches any of the resource IDs
                if filter_resource_id:
                    if filter_resource_id not in possible_resource_ids:
                        return False
            else:
                # For non-ODPS events, use standard fields
                possible_resource_ids = [
                    str(event_data.get("resource_id", "")),
                    str(event_data.get("contract_id", "")),
                    str(event_data.get("asset_id", "")),
                    str(event_data.get("id", "")),
                ]
                # Filter out empty strings
                possible_resource_ids = [
                    rid for rid in possible_resource_ids if rid and rid != "None"
                ]

                # Check if filter matches any of the resource IDs
                if filter_resource_id:
                    if filter_resource_id not in possible_resource_ids:
                        return False

        # Filter by execution_id (for virtualization events)
        if "execution_id" in self.filters:
            filter_execution_id = str(self.filters["execution_id"])
            event_data = event.get("data", {})
            event_execution_id = str(event_data.get("execution_id", ""))

            if filter_execution_id:
                if not event_execution_id or event_execution_id != filter_execution_id:
                    return False

        # Filter by query_execution_id (for virtualization query execution events)
        if "query_execution_id" in self.filters:
            filter_query_execution_id = str(self.filters["query_execution_id"])
            event_data = event.get("data", {})
            event_query_execution_id = str(event_data.get("query_execution_id", ""))

            if filter_query_execution_id and (
                not event_query_execution_id
                or event_query_execution_id != filter_query_execution_id
            ):
                return False

        # Filter by virtual_dataset_id (for virtualization events)
        if "virtual_dataset_id" in self.filters:
            filter_virtual_dataset_id = str(self.filters["virtual_dataset_id"])
            event_data = event.get("data", {})
            event_virtual_dataset_id = str(event_data.get("virtual_dataset_id", ""))

            if filter_virtual_dataset_id and (
                not event_virtual_dataset_id
                or event_virtual_dataset_id != filter_virtual_dataset_id
            ):
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

    async def send_error(self, error_message: str, request_id: str | None = None):
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
        self.last_activity = datetime.now(UTC)
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
                if (
                    self.last_activity
                    and (datetime.now(UTC) - self.last_activity).total_seconds()
                    > self.connection_timeout
                ):
                    logger.warning(
                        "websocket_connection_timeout",
                        user_id=str(self.scope.get("user").id) if self.scope.get("user") else None,
                        last_activity=self.last_activity.isoformat()
                        if self.last_activity
                        else None,
                        timeout_seconds=self.connection_timeout,
                    )
                    await self.close(code=4000)  # Normal closure due to timeout
                    break

                # Send ping if no pending ping
                if not self.pending_ping:
                    try:
                        ping_message = WebSocketMessage(
                            type=WebSocketMessageType.PING.value,
                            data={"timestamp": datetime.now(UTC).isoformat()},
                        )
                        await self.send_json_message(ping_message)
                        self.pending_ping = True

                        logger.debug(
                            "websocket_ping_sent",
                            user_id=str(self.scope.get("user").id)
                            if self.scope.get("user")
                            else None,
                        )
                    except Exception as e:
                        logger.error(
                            "websocket_ping_error",
                            error=str(e),
                            user_id=str(self.scope.get("user").id)
                            if self.scope.get("user")
                            else None,
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
                    time_since_pong = (datetime.now(UTC) - self.last_pong_received).total_seconds()
                    if time_since_pong > self.pong_timeout:
                        logger.warning(
                            "websocket_pong_timeout",
                            user_id=str(self.scope.get("user").id)
                            if self.scope.get("user")
                            else None,
                            time_since_pong=time_since_pong,
                            pong_timeout=self.pong_timeout,
                        )
                        await self.close(code=4000)  # Normal closure due to pong timeout
                        break

                # Check overall connection timeout
                if self.last_activity:
                    time_since_activity = (datetime.now(UTC) - self.last_activity).total_seconds()
                    if time_since_activity > self.connection_timeout:
                        logger.warning(
                            "websocket_connection_inactive_timeout",
                            user_id=str(self.scope.get("user").id)
                            if self.scope.get("user")
                            else None,
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
