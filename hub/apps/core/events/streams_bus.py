"""
Redis Streams-based Event Bus Implementation

Proof-of-concept implementation using Redis Streams as an alternative to Pub/Sub.

Redis Streams advantages:
- Built-in persistence (messages stored in Redis)
- Consumer groups (load balancing, at-least-once delivery)
- Message replay (read from any position)
- Message acknowledgment (ACK/NACK)
- Pending entries tracking (failed messages)
- Better scalability for high-throughput scenarios
"""

from __future__ import annotations

import json
import redis
import structlog
import time
from typing import Dict, Any, Optional, Callable, List
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta

from .schema import EventSchema
from .event_types import validate_event_data, CURRENT_EVENT_VERSION
from .models import Event, DeadLetterQueue, EventSubscription
from .deduplication import (
    generate_deduplication_key,
    check_event_duplicate,
    store_event_id,
)
from .metrics import (
    event_published_total,
    event_publish_failed_total,
    event_publish_duration_seconds,
    event_publish_redis_latency_seconds,
    event_persistence_duration_seconds,
    event_consumed_total,
    event_consume_failed_total,
    event_processing_duration_seconds,
    event_handler_retry_count,
    event_dlq_size,
    event_dlq_events_total,
    event_subscriptions_active,
    event_subscriptions_registered_total,
    event_bus_redis_connection_errors_total,
    event_bus_redis_publish_errors_total,
    get_tenant_id,
    get_error_type,
)

# OpenTelemetry tracing
try:
    from hub.apps.observability.tracing import get_tracer
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    _tracer = get_tracer(__name__)
    _trace_available = True
except ImportError:
    _tracer = None
    trace = None
    Status = None
    StatusCode = None
    _trace_available = False

logger = structlog.get_logger(__name__)


class EventStreamsError(Exception):
    """Base exception for event streams errors."""
    pass


class EventStreamsPublishError(EventStreamsError):
    """Error publishing event to stream."""
    pass


class EventStreamsSubscribeError(EventStreamsError):
    """Error subscribing to stream."""
    pass


class EventStreamsBus:
    """
    Redis Streams-based event bus implementation.

    Features:
    - Redis Streams for event delivery with persistence
    - Consumer groups for load balancing
    - Message acknowledgment (ACK/NACK)
    - Pending entries tracking
    - Event replay capabilities
    - PostgreSQL for additional persistence and audit
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize event streams bus.

        Args:
            redis_client: Optional Redis client (creates new if not provided)
        """
        self.redis_client = redis_client or self._create_redis_client()
        self.stream_prefix = getattr(settings, 'EVENT_BUS_STREAM_PREFIX', 'events:stream')
        self.consumer_group_prefix = getattr(settings, 'EVENT_BUS_CONSUMER_GROUP_PREFIX', 'event_consumers')
        self.enable_persistence = getattr(settings, 'EVENT_BUS_ENABLE_PERSISTENCE', True)
        self.max_retries = getattr(settings, 'EVENT_BUS_MAX_RETRIES', 3)
        self.stream_max_length = getattr(settings, 'EVENT_BUS_STREAM_MAX_LENGTH', 10000)  # Max messages per stream

    def _create_redis_client(self) -> redis.Redis:
        """
        Create Redis client with connection pooling from settings.
        """
        redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')

        pool_size = getattr(settings, 'EVENT_BUS_REDIS_POOL_SIZE', 50)
        max_connections = getattr(settings, 'EVENT_BUS_REDIS_MAX_CONNECTIONS', 100)
        socket_timeout = getattr(settings, 'EVENT_BUS_REDIS_SOCKET_TIMEOUT', 5)
        socket_connect_timeout = getattr(settings, 'EVENT_BUS_REDIS_SOCKET_CONNECT_TIMEOUT', 5)
        retry_on_timeout = getattr(settings, 'EVENT_BUS_REDIS_RETRY_ON_TIMEOUT', True)
        health_check_interval = getattr(settings, 'EVENT_BUS_REDIS_HEALTH_CHECK_INTERVAL', 30)

        try:
            pool = redis.ConnectionPool.from_url(
                redis_url,
                max_connections=max_connections,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_connect_timeout,
                retry_on_timeout=retry_on_timeout,
                health_check_interval=health_check_interval,
                decode_responses=True
            )

            return redis.Redis(
                connection_pool=pool,
                decode_responses=True
            )
        except Exception as e:
            error_type = get_error_type(None, e)
            event_bus_redis_connection_errors_total.labels(
                error_type=error_type
            ).inc()
            logger.error(
                "redis_connection_error",
                error=str(e),
                error_type=error_type,
                exc_info=True
            )
            raise

    def _get_stream_name(self, event_type: str) -> str:
        """
        Get Redis stream name for event type.

        Args:
            event_type: Event type (e.g., 'contract.created')

        Returns:
            Stream name (e.g., 'events:stream:contract:created')
        """
        # Convert event type to stream name
        # e.g., 'contract.created' -> 'events:stream:contract:created'
        stream_name = f"{self.stream_prefix}:{event_type.replace('.', ':')}"
        return stream_name

    def publish(
        self,
        event_type: str,
        data: Dict[str, Any],
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        event_version: str = CURRENT_EVENT_VERSION
    ) -> str:
        """
        Publish an event to the Redis stream.

        Args:
            event_type: Event type (e.g., 'contract.created')
            data: Event data payload
            tenant_id: Tenant UUID (optional)
            user_id: User UUID (optional)
            request_id: Request ID for tracing (optional)
            correlation_id: Correlation ID for tracing (optional)
            causation_id: Event ID that caused this event (optional)
            tags: Tags for filtering (optional)
            event_version: Schema version (default: '1.0.0')

        Returns:
            Event ID (UUID string)

        Raises:
            EventStreamsPublishError: If event publishing fails
        """
        start_time = time.time()
        tenant_label = get_tenant_id(tenant_id)
        status = "success"
        error_type = None

        # Create tracing span
        span = None
        if _tracer:
            span = _tracer.start_span(
                name=f"event_streams.publish",
                attributes={
                    "event.type": event_type,
                    "event.tenant_id": tenant_label,
                    "event.version": event_version,
                }
            )

        try:
            # Validate event data against schema
            is_valid, error = validate_event_data(event_type, data)
            if not is_valid:
                status = "validation_failed"
                error_type = "validation_error"
                if span and _trace_available:
                    span.set_attribute("event.validation_error", error)
                    span.set_status(Status(StatusCode.ERROR, error))
                    span.end()
                raise EventStreamsPublishError(f"Invalid event data for {event_type}: {error}")

            # Build event
            event = EventSchema.build_event(
                event_type=event_type,
                data=data,
                tenant_id=tenant_id,
                user_id=user_id,
                request_id=request_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                tags=tags,
                event_version=event_version
            )

            # Validate event
            is_valid, error = EventSchema.validate_event(event)
            if not is_valid:
                status = "validation_failed"
                error_type = "validation_error"
                if span and _trace_available:
                    span.set_attribute("event.validation_error", error)
                    span.set_status(Status(StatusCode.ERROR, error))
                    span.end()
                raise EventStreamsPublishError(f"Invalid event: {error}")

            event_id = event["event_id"]

            if span:
                span.set_attribute("event.id", event_id)
                if correlation_id:
                    span.set_attribute("event.correlation_id", correlation_id)
                if causation_id:
                    span.set_attribute("event.causation_id", causation_id)

            # Check persistence setting dynamically (for test overrides)
            enable_persistence = getattr(settings, 'EVENT_BUS_ENABLE_PERSISTENCE', True)

            # Persist event to PostgreSQL
            if enable_persistence:
                persist_start = time.time()
                try:
                    self._persist_event(event)
                    persist_duration = time.time() - persist_start
                    event_persistence_duration_seconds.labels(
                        event_type=event_type,
                        status="success",
                        tenant_id=tenant_label
                    ).observe(persist_duration)
                except Exception as persist_error:
                    persist_duration = time.time() - persist_start
                    event_persistence_duration_seconds.labels(
                        event_type=event_type,
                        status="failed",
                        tenant_id=tenant_label
                    ).observe(persist_duration)
                    raise

            # Publish to Redis Stream
            stream_name = self._get_stream_name(event_type)
            event_json = json.dumps(event)

            redis_start = time.time()
            try:
                # Use XADD to add event to stream
                # Format: XADD stream_name MAXLEN ~ max_length * field value ...
                # Using '*' for auto-generated message ID
                message_id = self.redis_client.xadd(
                    stream_name,
                    {
                        'event': event_json,
                        'event_id': event_id,
                        'event_type': event_type,
                        'timestamp': event['timestamp']
                    },
                    maxlen=self.stream_max_length,
                    approximate=True  # Use ~ for approximate trimming
                )
                redis_latency = time.time() - redis_start
                event_publish_redis_latency_seconds.labels(
                    event_type=event_type,
                    tenant_id=tenant_label
                ).observe(redis_latency)

                logger.info(
                    "event_published_to_stream",
                    event_id=event_id,
                    event_type=event_type,
                    stream_name=stream_name,
                    message_id=message_id,
                    tenant_id=tenant_id
                )
            except Exception as e:
                redis_latency = time.time() - redis_start
                error_type = get_error_type(None, e)
                event_bus_redis_publish_errors_total.labels(
                    event_type=event_type,
                    error_type=error_type,
                    tenant_id=tenant_label
                ).inc()

                logger.error(
                    "event_stream_publish_error",
                    event_id=event_id,
                    event_type=event_type,
                    stream_name=stream_name,
                    error=str(e),
                    exc_info=True
                )
                raise EventStreamsPublishError(f"Failed to publish event to stream: {e}") from e

            # Record success metrics
            publish_duration = time.time() - start_time
            event_published_total.labels(
                event_type=event_type,
                status=status,
                tenant_id=tenant_label
            ).inc()
            event_publish_duration_seconds.labels(
                event_type=event_type,
                status=status,
                tenant_id=tenant_label
            ).observe(publish_duration)

            if span and _trace_available:
                span.set_attribute("event.publish_duration_seconds", publish_duration)
                span.set_attribute("event.message_id", str(message_id))
                span.set_status(Status(StatusCode.OK))
                span.end()

            return event_id

        except Exception as e:
            error_type = get_error_type(None, e)
            status = "failed"
            publish_duration = time.time() - start_time

            # Record failure metrics
            event_publish_failed_total.labels(
                event_type=event_type,
                error_type=error_type,
                tenant_id=tenant_label
            ).inc()
            event_publish_duration_seconds.labels(
                event_type=event_type,
                status=status,
                tenant_id=tenant_label
            ).observe(publish_duration)

            if span and _trace_available:
                span.set_attribute("event.error_type", error_type)
                span.set_attribute("event.error_message", str(e))
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                span.end()

            logger.error(
                "event_stream_publish_error",
                event_type=event_type,
                error=str(e),
                exc_info=True
            )
            raise EventStreamsPublishError(f"Failed to publish event: {e}") from e

    def _persist_event(self, event: Dict[str, Any]) -> Event:
        """
        Persist event to PostgreSQL.

        Args:
            event: Event dictionary

        Returns:
            Event model instance
        """
        try:
            with transaction.atomic():
                event_obj = Event.objects.create(
                    event_id=event["event_id"],
                    event_type=event["event_type"],
                    event_version=event["event_version"],
                    timestamp=datetime.fromisoformat(event["timestamp"].replace('Z', '+00:00')),
                    source_service=event["source"]["service"],
                    tenant_id=event["source"].get("tenant_id"),
                    user_id=event["source"].get("user_id"),
                    request_id=event["source"].get("request_id"),
                    data=event["data"],
                    metadata=event.get("metadata", {})
                )
                return event_obj
        except Exception as e:
            logger.error(
                "event_persistence_error",
                event_id=event.get("event_id"),
                error=str(e),
                exc_info=True
            )
            raise

    def create_consumer_group(
        self,
        stream_name: str,
        group_name: str,
        start_id: str = "0"
    ) -> bool:
        """
        Create a consumer group for a stream.

        Args:
            stream_name: Stream name
            group_name: Consumer group name
            start_id: Starting message ID (default: "0" for beginning)

        Returns:
            True if created, False if already exists
        """
        try:
            self.redis_client.xgroup_create(
                stream_name,
                group_name,
                id=start_id,
                mkstream=True  # Create stream if it doesn't exist
            )
            logger.info(
                "consumer_group_created",
                stream_name=stream_name,
                group_name=group_name,
                start_id=start_id
            )
            return True
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" in str(e):
                # Group already exists
                logger.debug(
                    "consumer_group_exists",
                    stream_name=stream_name,
                    group_name=group_name
                )
                return False
            raise

    def subscribe(
        self,
        subscriber_name: str,
        event_type_pattern: str,
        handler: Callable[[Dict[str, Any]], None],
        is_active: bool = True
    ) -> None:
        """
        Subscribe to events matching a pattern using consumer groups.

        Args:
            subscriber_name: Unique subscriber identifier
            event_type_pattern: Event type pattern (supports wildcards, e.g., 'contract.*')
            handler: Callback function to handle events
            is_active: Whether subscription is active
        """
        status = "success"
        try:
            # Register subscription in database
            subscription, created = EventSubscription.objects.update_or_create(
                subscriber_name=subscriber_name,
                event_type_pattern=event_type_pattern,
                defaults={"is_active": is_active}
            )

            # Update metrics
            if is_active:
                event_subscriptions_active.labels(
                    event_type_pattern=event_type_pattern,
                    subscriber_name=subscriber_name
                ).inc()

            event_subscriptions_registered_total.labels(
                event_type_pattern=event_type_pattern,
                subscriber_name=subscriber_name,
                status=status
            ).inc()

            logger.info(
                "event_subscription_registered",
                subscriber_name=subscriber_name,
                event_type_pattern=event_type_pattern
            )

        except Exception as e:
            status = "failed"
            error_str = str(e)
            is_db_error = (
                "relation" in error_str.lower() or
                "does not exist" in error_str.lower() or
                "connection refused" in error_str.lower() or
                "ProgrammingError" in str(type(e).__name__) or
                "OperationalError" in str(type(e).__name__)
            )
            is_async_error = (
                "async context" in error_str.lower() or
                "sync_to_async" in error_str.lower() or
                "async_to_sync" in error_str.lower() or
                "cannot call this from an async context" in error_str.lower()
            )

            if is_db_error or is_async_error:
                logger.debug(
                    "event_subscribe_deferred",
                    subscriber_name=subscriber_name,
                    event_type_pattern=event_type_pattern,
                    reason="database_not_ready" if is_db_error else "async_context",
                    error_type=type(e).__name__
                )
                return

            event_subscriptions_registered_total.labels(
                event_type_pattern=event_type_pattern,
                subscriber_name=subscriber_name,
                status=status
            ).inc()

            logger.error(
                "event_subscribe_error",
                subscriber_name=subscriber_name,
                event_type_pattern=event_type_pattern,
                error=str(e),
                exc_info=True
            )
            raise EventStreamsSubscribeError(f"Failed to subscribe: {e}") from e

    def start_listening(
        self,
        subscriber_name: str,
        handler: Callable[[Dict[str, Any]], None],
        consumer_group: Optional[str] = None,
        block_ms: int = 1000
    ) -> None:
        """
        Start listening for events using consumer groups.

        Args:
            subscriber_name: Subscriber identifier
            handler: Event handler function
            consumer_group: Consumer group name (defaults to subscriber_name)
            block_ms: Blocking time in milliseconds (default: 1000ms)
        """
        try:
            # Get active subscriptions for this subscriber
            subscriptions = EventSubscription.objects.filter(
                subscriber_name=subscriber_name,
                is_active=True
            )

            if not subscriptions.exists():
                logger.warning(
                    "no_active_subscriptions",
                    subscriber_name=subscriber_name
                )
                return

            # Use subscriber_name as consumer group if not specified
            if consumer_group is None:
                consumer_group = f"{self.consumer_group_prefix}:{subscriber_name}"

            # Create consumer group for each stream
            streams = {}
            for subscription in subscriptions:
                event_type = subscription.event_type_pattern
                stream_name = self._get_stream_name(event_type)

                # Create consumer group if it doesn't exist
                self.create_consumer_group(stream_name, consumer_group)

                # Track stream for reading
                streams[stream_name] = event_type

            logger.info(
                "event_listening_started",
                subscriber_name=subscriber_name,
                consumer_group=consumer_group,
                streams=list(streams.keys())
            )

            # Start listening (blocking)
            self._listen_streams(streams, consumer_group, subscriber_name, handler, block_ms)

        except Exception as e:
            logger.error(
                "event_listening_error",
                subscriber_name=subscriber_name,
                error=str(e),
                exc_info=True
            )
            raise EventStreamsSubscribeError(f"Failed to start listening: {e}") from e

    def _listen_streams(
        self,
        streams: Dict[str, str],
        consumer_group: str,
        subscriber_name: str,
        handler: Callable[[Dict[str, Any]], None],
        block_ms: int
    ) -> None:
        """
        Listen for events from streams using consumer groups.

        Args:
            streams: Dictionary mapping stream names to event types
            consumer_group: Consumer group name
            subscriber_name: Subscriber identifier
            handler: Event handler function
            block_ms: Blocking time in milliseconds
        """
        consumer_name = f"{subscriber_name}_{id(self)}"  # Unique consumer name

        while True:
            try:
                # Read from streams using XREADGROUP
                # Format: XREADGROUP GROUP group consumer STREAMS stream1 stream2 ... > > ...
                # '>' means: only messages that were never delivered to any consumer
                # Convert streams dict to use ">" as ID for each stream
                streams_with_ids = {stream: ">" for stream in streams.keys()}
                messages = self.redis_client.xreadgroup(
                    consumer_group,
                    consumer_name,
                    streams_with_ids,
                    count=10,  # Read up to 10 messages at a time
                    block=block_ms
                )

                for stream_name, stream_messages in messages:
                    event_type = streams.get(stream_name, "unknown")

                    for message_id, message_data in stream_messages:
                        try:
                            # Parse event from message
                            event_json = message_data.get('event', '{}')
                            event = json.loads(event_json)

                            # Handle event
                            self._handle_event(subscriber_name, event, handler)

                            # Acknowledge message
                            self.redis_client.xack(stream_name, consumer_group, message_id)

                            # Record success metrics
                            event_consumed_total.labels(
                                event_type=event_type,
                                subscriber_name=subscriber_name
                            ).inc()

                        except json.JSONDecodeError as e:
                            logger.error(
                                "event_decode_error",
                                subscriber_name=subscriber_name,
                                stream_name=stream_name,
                                message_id=message_id,
                                error=str(e)
                            )
                            # NACK message (don't acknowledge)
                            # Message will be retried or sent to DLQ
                        except Exception as e:
                            logger.error(
                                "event_handler_error",
                                subscriber_name=subscriber_name,
                                stream_name=stream_name,
                                message_id=message_id,
                                error=str(e),
                                exc_info=True
                            )
                            # Send to dead letter queue
                            try:
                                event_json = message_data.get('event', '{}')
                                event = json.loads(event_json)
                                self._send_to_dlq(subscriber_name, event, str(e))
                            except Exception:
                                pass

                            # Record failure metrics
                            event_consume_failed_total.labels(
                                event_type=event_type,
                                subscriber_name=subscriber_name
                            ).inc()

            except redis.exceptions.ConnectionError as e:
                logger.error(
                    "redis_connection_error",
                    subscriber_name=subscriber_name,
                    error=str(e),
                    exc_info=True
                )
                # Wait before retrying
                time.sleep(1)
            except Exception as e:
                logger.error(
                    "event_listening_error",
                    subscriber_name=subscriber_name,
                    error=str(e),
                    exc_info=True
                )
                # Wait before retrying
                time.sleep(1)

    def _handle_event(
        self,
        subscriber_name: str,
        event: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        """
        Handle event with retry logic.

        Args:
            subscriber_name: Subscriber identifier
            event: Event dictionary
            handler: Event handler function
        """
        start_time = time.time()
        retries = 0

        while retries <= self.max_retries:
            try:
                handler(event)
                processing_duration = time.time() - start_time
                event_processing_duration_seconds.labels(
                    event_type=event.get("event_type", "unknown"),
                    subscriber_name=subscriber_name,
                    status="success"
                ).observe(processing_duration)
                return
            except Exception as e:
                retries += 1
                event_handler_retry_count.labels(
                    event_type=event.get("event_type", "unknown"),
                    subscriber_name=subscriber_name
                ).inc()

                if retries > self.max_retries:
                    processing_duration = time.time() - start_time
                    event_processing_duration_seconds.labels(
                        event_type=event.get("event_type", "unknown"),
                        subscriber_name=subscriber_name,
                        status="failed"
                    ).observe(processing_duration)
                    raise

                # Exponential backoff
                time.sleep(2 ** retries)

    def _send_to_dlq(self, subscriber_name: str, event: Dict[str, Any], error: str) -> None:
        """
        Send failed event to dead letter queue.

        Args:
            subscriber_name: Subscriber identifier
            event: Event dictionary
            error: Error message
        """
        try:
            DeadLetterQueue.objects.create(
                event_id=event.get("event_id"),
                event_type=event.get("event_type", "unknown"),
                subscriber_name=subscriber_name,
                error_message=error,
                event_data=event
            )
            event_dlq_events_total.labels(
                event_type=event.get("event_type", "unknown"),
                subscriber_name=subscriber_name
            ).inc()
        except Exception as e:
            logger.error(
                "dlq_error",
                subscriber_name=subscriber_name,
                error=str(e),
                exc_info=True
            )

    def get_pending_messages(
        self,
        stream_name: str,
        consumer_group: str,
        consumer_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get pending messages for a consumer group.

        Args:
            stream_name: Stream name
            consumer_group: Consumer group name
            consumer_name: Optional consumer name filter

        Returns:
            List of pending messages
        """
        try:
            if consumer_name:
                pending = self.redis_client.xpending_range(
                    stream_name,
                    consumer_group,
                    min="-",
                    max="+",
                    count=100,
                    consumername=consumer_name
                )
            else:
                pending = self.redis_client.xpending(stream_name, consumer_group)

            return pending
        except Exception as e:
            logger.error(
                "pending_messages_error",
                stream_name=stream_name,
                consumer_group=consumer_group,
                error=str(e),
                exc_info=True
            )
            return []

    def replay_events(
        self,
        stream_name: str,
        start_id: str = "0",
        end_id: str = "+",
        count: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Replay events from a stream.

        Args:
            stream_name: Stream name
            start_id: Starting message ID (default: "0")
            end_id: Ending message ID (default: "+" for latest)
            count: Maximum number of messages to read (optional)

        Returns:
            List of events
        """
        try:
            kwargs = {}
            if count:
                kwargs['count'] = count

            messages = self.redis_client.xrange(stream_name, start_id, end_id, **kwargs)

            events = []
            for message_id, message_data in messages:
                try:
                    event_json = message_data.get('event', '{}')
                    event = json.loads(event_json)
                    events.append(event)
                except json.JSONDecodeError:
                    continue

            return events
        except Exception as e:
            logger.error(
                "replay_events_error",
                stream_name=stream_name,
                error=str(e),
                exc_info=True
            )
            return []


def get_event_streams_bus(redis_client: Optional[redis.Redis] = None) -> EventStreamsBus:
    """
    Get global event streams bus instance.

    Args:
        redis_client: Optional Redis client

    Returns:
        EventStreamsBus instance
    """
    if not hasattr(get_event_streams_bus, '_instance'):
        get_event_streams_bus._instance = EventStreamsBus(redis_client=redis_client)
    return get_event_streams_bus._instance

