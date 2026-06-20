"""
Event Bus Implementation

Redis-based event bus with PostgreSQL persistence, replay, and dead letter queue support.
"""

from __future__ import annotations

import json
import threading as _threading
import time
import uuid as _uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

import redis
import structlog
from django.conf import settings
from django.db import transaction
from django.db.utils import ProgrammingError
from django.utils import timezone

from .acknowledgment import (
    acknowledge_event,
    cleanup_timeout_events,
    mark_event_pending,
    mark_event_processing,
)
from .deduplication import (
    check_event_duplicate,
    generate_deduplication_key,
    store_event_id,
)
from .event_types import CURRENT_EVENT_VERSION, validate_event_data
from .metrics import (
    event_bus_redis_connection_errors_total,
    event_bus_redis_publish_errors_total,
    event_consume_failed_total,
    event_consumed_total,
    event_dlq_events_total,
    event_dlq_size,
    event_handler_retry_count,
    event_latency_seconds,
    event_persistence_duration_seconds,
    event_processing_duration_seconds,
    event_publish_duration_seconds,
    event_publish_failed_total,
    event_publish_redis_latency_seconds,
    event_published_total,
    event_queue_depth,
    event_retry_attempts_total,
    event_subscriptions_active,
    event_subscriptions_registered_total,
    get_error_type,
    get_tenant_id,
)
from .models import DeadLetterQueue, Event, EventSubscription
from .persistence_tasks import persist_event_async
from .retry_policy import get_retry_policy
from .schema import EventSchema
from .write_behind import get_write_behind_buffer

# OpenTelemetry tracing
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    from hub.apps.observability.tracing import get_tracer

    _tracer = get_tracer(__name__)
    _trace_available = True
except ImportError:
    _tracer = None
    trace = None
    Status = None
    StatusCode = None
    _trace_available = False

logger = structlog.get_logger(__name__)


def _validate_optional_uuid(value: str | None, field_name: str) -> None:
    """Raise ``ValueError`` if *value* is not a valid UUID or None/empty.

    This is called at the top of :meth:`EventBus.publish` so invalid
    tenant_id / user_id values fail fast with a clear error instead of
    cascading into schema validation or DB persistence — both of which
    log at ERROR level and obscure the root cause.
    """
    if value is None or value == "":
        return
    try:
        _uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ValueError(f"{field_name} must be a valid UUID or None; got {value!r}") from None


def _run_with_timeout(func, args=(), timeout_seconds=30):
    """Run *func* in a daemon thread with a timeout.

    Returns the result on success, raises the handler's exception on
    failure, or raises ``TimeoutError`` if the handler exceeds
    *timeout_seconds*.

    **Thread-leak note**: Python threads cannot be forcibly killed.  If
    the handler times out, the daemon thread continues executing until it
    completes naturally.  Daemon threads are cleaned up on process exit,
    but may consume resources in the interim.  Handlers that respect a
    cooperative ``_timeout_event`` (``threading.Event``) can exit early.
    """
    result = [None]
    exception = [None]
    _timeout_event = _threading.Event()

    def target():
        try:
            result[0] = func(*args)
        except Exception as exc:
            exception[0] = exc

    thread = _threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        _timeout_event.set()  # signal cooperative cancellation
        logger.warning(
            "event_handler_timeout",
            timeout_seconds=timeout_seconds,
            thread_name=thread.name,
        )
        raise TimeoutError(f"Event handler timed out after {timeout_seconds}s")
    if exception[0]:
        raise exception[0]
    return result[0]


class EventBusError(Exception):
    """Base exception for event bus errors."""


class EventPublishError(EventBusError):
    """Error publishing event."""


class EventSubscribeError(EventBusError):
    """Error subscribing to events."""


class EventBus:
    """
    Redis-based event bus with PostgreSQL persistence.

    Features:
    - Redis Pub/Sub for real-time event delivery
    - PostgreSQL for event persistence and replay
    - Dead letter queue for failed events
    - Event subscription management
    """

    def __init__(
        self,
        redis_client: redis.Redis | None = None,
        *,
        force_sync_persistence: bool = False,
    ):
        """
        Initialize event bus.

        Args:
            redis_client: Optional Redis client (creates new if not provided)
            force_sync_persistence: If True, always persist synchronously (for tests).
        """
        self.redis_client = redis_client or self._create_redis_client()
        self.channel_prefix = getattr(settings, "EVENT_BUS_CHANNEL_PREFIX", "events")
        self.enable_persistence = getattr(settings, "EVENT_BUS_ENABLE_PERSISTENCE", True)
        self.max_retries = getattr(settings, "EVENT_BUS_MAX_RETRIES", 3)
        self.force_sync_persistence = force_sync_persistence

    def _create_redis_client(self) -> redis.Redis:
        """
        Create Redis client with connection pooling from settings.

        Uses REDIS_EVENTS_URL (separate Redis instance for events) with fallback to REDIS_URL
        for backward compatibility. Uses connection pooling for better performance and resource management.
        """
        # Use REDIS_EVENTS_URL if available, fallback to REDIS_URL for backward compatibility
        redis_url = getattr(settings, "REDIS_EVENTS_URL", None)
        if redis_url is None:
            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6381/0")
            logger.info("Using REDIS_URL as fallback for event bus", redis_url=redis_url)

        # Connection pool configuration
        getattr(settings, "EVENT_BUS_REDIS_POOL_SIZE", 50)
        max_connections = getattr(settings, "EVENT_BUS_REDIS_MAX_CONNECTIONS", 100)
        socket_timeout = getattr(settings, "EVENT_BUS_REDIS_SOCKET_TIMEOUT", 5)
        socket_connect_timeout = getattr(settings, "EVENT_BUS_REDIS_SOCKET_CONNECT_TIMEOUT", 5)
        retry_on_timeout = getattr(settings, "EVENT_BUS_REDIS_RETRY_ON_TIMEOUT", True)
        health_check_interval = getattr(settings, "EVENT_BUS_REDIS_HEALTH_CHECK_INTERVAL", 30)

        try:
            # Create connection pool
            pool = redis.ConnectionPool.from_url(
                redis_url,
                max_connections=max_connections,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_connect_timeout,
                retry_on_timeout=retry_on_timeout,
                health_check_interval=health_check_interval,
                decode_responses=True,
            )

            # Create Redis client with connection pool
            return redis.Redis(connection_pool=pool, decode_responses=True)
        except Exception as e:
            error_type = get_error_type(None, e)
            event_bus_redis_connection_errors_total.labels(error_type=error_type).inc()
            logger.error(
                "redis_connection_error",
                error=str(e),
                error_type=error_type,
                redis_url=redis_url,
                exc_info=True,
            )
            raise

    def publish(
        self,
        event_type: str,
        data: dict[str, Any],
        tenant_id: str | None = None,
        user_id: str | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        tags: list[str] | None = None,
        event_version: str = CURRENT_EVENT_VERSION,
        service_name: str | None = None,
    ) -> str:
        """
        Publish an event to the event bus.

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
            EventPublishError: If event publishing fails
            ValueError: If tenant_id or user_id is not a valid UUID or None
        """
        # Validate UUID fields early so invalid values don't cascade into
        # schema validation or DB persistence — both of which log at ERROR
        # level.  Catching them here gives callers a clean ValueError and
        # keeps ERROR logs for actual system failures.
        _validate_optional_uuid(tenant_id, "tenant_id")
        _validate_optional_uuid(user_id, "user_id")

        start_time = time.time()
        tenant_label = get_tenant_id(tenant_id)
        status = "success"
        error_type = None

        # Create tracing span
        span = None
        if _tracer:
            span = _tracer.start_span(
                name="event_bus.publish",
                attributes={
                    "event.type": event_type,
                    "event.tenant_id": tenant_label,
                    "event.version": event_version,
                },
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
                raise EventPublishError(f"Invalid event data for {event_type}: {error}")

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
                event_version=event_version,
                service_name=service_name,
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
                raise EventPublishError(f"Invalid event: {error}")

            event_id = event["event_id"]

            if span:
                span.set_attribute("event.id", event_id)
                if correlation_id:
                    span.set_attribute("event.correlation_id", correlation_id)
                if causation_id:
                    span.set_attribute("event.causation_id", causation_id)

            # Check persistence setting dynamically (for test overrides)
            enable_persistence = getattr(settings, "EVENT_BUS_ENABLE_PERSISTENCE", True)
            use_async_persistence = getattr(settings, "EVENT_BUS_ASYNC_PERSISTENCE", True)
            use_write_behind = getattr(settings, "EVENT_BUS_WRITE_BEHIND_ENABLED", False)

            # Persist event to PostgreSQL (write-behind, async, or sync based on configuration)
            if enable_persistence:
                if self.force_sync_persistence:
                    # Tests: always persist synchronously so Event.objects.get() sees the row
                    persist_start = time.time()
                    try:
                        self._persist_event(event)
                        persist_duration = time.time() - persist_start
                        event_persistence_duration_seconds.labels(
                            event_type=event_type, status="success", tenant_id=tenant_label
                        ).observe(persist_duration)
                    except ProgrammingError as persist_error:
                        persist_duration = time.time() - persist_start
                        event_persistence_duration_seconds.labels(
                            event_type=event_type, status="failed", tenant_id=tenant_label
                        ).observe(persist_duration)
                        err_str = str(persist_error)
                        if "does not exist" in err_str or "relation" in err_str.lower():
                            logger.warning(
                                "event_persistence_skipped_table_missing",
                                event_id=event_id,
                                event_type=event_type,
                                error=err_str,
                                message="Events table missing; continuing without persistence",
                            )
                        else:
                            logger.error(
                                "event_persistence_error",
                                event_id=event_id,
                                event_type=event_type,
                                error=err_str,
                                exc_info=True,
                            )
                            raise
                    except Exception as persist_error:
                        persist_duration = time.time() - persist_start
                        event_persistence_duration_seconds.labels(
                            event_type=event_type, status="failed", tenant_id=tenant_label
                        ).observe(persist_duration)
                        logger.error(
                            "event_persistence_error",
                            event_id=event_id,
                            event_type=event_type,
                            error=str(persist_error),
                            exc_info=True,
                        )
                        raise
                elif use_write_behind:
                    # Write-behind pattern: buffer events and flush in batches
                    try:
                        buffer = get_write_behind_buffer()
                        buffer.add_event(event)
                        logger.debug(
                            "event_persistence_buffered_write_behind",
                            event_id=event_id,
                            event_type=event_type,
                            buffer_size=buffer.get_buffer_size(),
                        )
                    except Exception as write_behind_error:
                        # If write-behind fails, fall back to async persistence
                        logger.warning(
                            "event_persistence_write_behind_failed_fallback",
                            event_id=event_id,
                            event_type=event_type,
                            error=str(write_behind_error),
                            message="Falling back to async persistence",
                        )
                        try:
                            persist_event_async.delay(event)
                            logger.debug(
                                "event_persistence_queued_async",
                                event_id=event_id,
                                event_type=event_type,
                            )
                        except Exception as persist_error:
                            # If async queue fails, fall back to sync persistence
                            logger.warning(
                                "event_persistence_async_failed_fallback",
                                event_id=event_id,
                                event_type=event_type,
                                error=str(persist_error),
                                message="Falling back to synchronous persistence",
                            )
                            persist_start = time.time()
                            try:
                                self._persist_event(event)
                                persist_duration = time.time() - persist_start
                                event_persistence_duration_seconds.labels(
                                    event_type=event_type, status="success", tenant_id=tenant_label
                                ).observe(persist_duration)
                            except Exception as sync_persist_error:
                                persist_duration = time.time() - persist_start
                                event_persistence_duration_seconds.labels(
                                    event_type=event_type, status="failed", tenant_id=tenant_label
                                ).observe(persist_duration)
                                # Don't raise - allow event to be published even if persistence fails
                                logger.error(
                                    "event_persistence_sync_failed",
                                    event_id=event_id,
                                    event_type=event_type,
                                    error=str(sync_persist_error),
                                    exc_info=True,
                                )
                elif use_async_persistence:
                    # Queue async persistence task (non-blocking)
                    try:
                        persist_event_async.delay(event)
                        logger.debug(
                            "event_persistence_queued_async",
                            event_id=event_id,
                            event_type=event_type,
                        )
                    except Exception as persist_error:
                        # If async queue fails, fall back to sync persistence
                        logger.warning(
                            "event_persistence_async_failed_fallback",
                            event_id=event_id,
                            event_type=event_type,
                            error=str(persist_error),
                            message="Falling back to synchronous persistence",
                        )
                        persist_start = time.time()
                        try:
                            self._persist_event(event)
                            persist_duration = time.time() - persist_start
                            event_persistence_duration_seconds.labels(
                                event_type=event_type, status="success", tenant_id=tenant_label
                            ).observe(persist_duration)
                        except Exception as sync_persist_error:
                            persist_duration = time.time() - persist_start
                            event_persistence_duration_seconds.labels(
                                event_type=event_type, status="failed", tenant_id=tenant_label
                            ).observe(persist_duration)
                            # Don't raise - allow event to be published even if persistence fails
                            logger.error(
                                "event_persistence_sync_failed",
                                event_id=event_id,
                                event_type=event_type,
                                error=str(sync_persist_error),
                                exc_info=True,
                            )
                else:
                    # Synchronous persistence (original behavior)
                    persist_start = time.time()
                    try:
                        self._persist_event(event)
                        persist_duration = time.time() - persist_start
                        event_persistence_duration_seconds.labels(
                            event_type=event_type, status="success", tenant_id=tenant_label
                        ).observe(persist_duration)
                    except Exception as persist_error:
                        persist_duration = time.time() - persist_start
                        event_persistence_duration_seconds.labels(
                            event_type=event_type, status="failed", tenant_id=tenant_label
                        ).observe(persist_duration)
                        logger.error(
                            "event_persistence_error",
                            event_id=event_id,
                            event_type=event_type,
                            error=str(persist_error),
                            exc_info=True,
                        )
                        # Re-raise when persistence is enabled so callers (e.g. tests) see the error
                        if enable_persistence:
                            raise

            # Publish to Redis
            channel = self._get_channel(event_type)
            event_json = json.dumps(event)

            redis_start = time.time()
            try:
                self.redis_client.publish(channel, event_json)
                redis_latency = time.time() - redis_start
                event_publish_redis_latency_seconds.labels(
                    event_type=event_type, tenant_id=tenant_label
                ).observe(redis_latency)

                logger.info(
                    "event_published",
                    event_id=event_id,
                    event_type=event_type,
                    channel=channel,
                    tenant_id=tenant_id,
                )
            except Exception as e:
                redis_latency = time.time() - redis_start
                error_type = get_error_type(None, e)
                event_bus_redis_publish_errors_total.labels(
                    event_type=event_type, error_type=error_type, tenant_id=tenant_label
                ).inc()

                # Redis publish failures are operational events — the system
                # gracefully falls back to DB persistence.  WARNING keeps CI
                # output clean while still recording the event.
                logger.warning(
                    "event_publish_redis_error",
                    event_id=event_id,
                    event_type=event_type,
                    error=str(e),
                )
                # If persistence is enabled, persist event even if Redis publish fails
                # This ensures events are not lost when Redis is unavailable
                if enable_persistence:
                    # Event already persisted above, so we just log the Redis failure
                    status = "redis_failed_persisted"
                else:
                    # If persistence is disabled and Redis fails, we can't recover
                    status = "redis_failed"
                    raise EventPublishError(f"Failed to publish event to Redis: {e}")

            # Record success metrics
            publish_duration = time.time() - start_time
            event_published_total.labels(
                event_type=event_type, status=status, tenant_id=tenant_label
            ).inc()
            event_publish_duration_seconds.labels(
                event_type=event_type, status=status, tenant_id=tenant_label
            ).observe(publish_duration)

            if span and _trace_available:
                span.set_attribute("event.publish_duration_seconds", publish_duration)
                span.set_status(Status(StatusCode.OK))
                span.end()

            return event_id

        except Exception as e:
            error_type = get_error_type(None, e)
            status = "failed"
            publish_duration = time.time() - start_time

            # Record failure metrics
            event_publish_failed_total.labels(
                event_type=event_type, error_type=error_type, tenant_id=tenant_label
            ).inc()
            event_publish_duration_seconds.labels(
                event_type=event_type, status=status, tenant_id=tenant_label
            ).observe(publish_duration)

            if span and _trace_available:
                span.set_attribute("event.error_type", error_type)
                span.set_attribute("event.error_message", str(e))
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                span.end()

            logger.error("event_publish_error", event_type=event_type, error=str(e), exc_info=True)
            raise EventPublishError(f"Failed to publish event: {e}") from e

    def _persist_event(self, event: dict[str, Any]) -> Event:
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
                    timestamp=datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")),
                    source_service=event["source"]["service"],
                    tenant_id=event["source"].get("tenant_id"),
                    user_id=event["source"].get("user_id"),
                    request_id=event["source"].get("request_id"),
                    data=event["data"],
                    metadata=event.get("metadata", {}),
                )
                return event_obj
        except Exception as e:
            logger.error(
                "event_persistence_error",
                event_id=event.get("event_id"),
                error=str(e),
                exc_info=True,
            )
            # Re-raise if persistence is enabled (use runtime settings for test overrides)
            enable_persistence = getattr(settings, "EVENT_BUS_ENABLE_PERSISTENCE", True)
            if enable_persistence:
                raise

    def subscribe(
        self,
        subscriber_name: str,
        event_type_pattern: str,
        handler: Callable[[dict[str, Any]], None],
        is_active: bool = True,
    ) -> None:
        """
        Subscribe to events matching a pattern.

        Note: This registers the subscription but does not start listening.

        Skips database access during test mode to prevent timeouts during Django setup.
        Use start_listening() or run in a background worker to process events.

        Args:
            subscriber_name: Unique subscriber identifier
            event_type_pattern: Event type pattern (supports wildcards, e.g., 'contract.*')
            handler: Callback function to handle events
            is_active: Whether subscription is active

        Raises:
            EventSubscribeError: If subscription fails
        """
        # Check if database connection is available (works during tests too)
        db_available = False
        try:
            from django.db import connection

            connection.ensure_connection()
            db_available = True
        except Exception:
            db_available = False

        status = "success"
        try:
            # Register subscription in database (skip if database not available)
            if db_available:
                _subscription, created = EventSubscription.objects.update_or_create(
                    subscriber_name=subscriber_name,
                    event_type_pattern=event_type_pattern,
                    defaults={"is_active": is_active},
                )
            else:
                # Database not available - defer subscription registration
                logger.debug(
                    "event_subscription_deferred",
                    subscriber_name=subscriber_name,
                    event_type_pattern=event_type_pattern,
                    reason="database_not_available",
                )

            # Update metrics
            if is_active:
                event_subscriptions_active.labels(
                    event_type_pattern=event_type_pattern, subscriber_name=subscriber_name
                ).inc()

            event_subscriptions_registered_total.labels(
                event_type_pattern=event_type_pattern,
                subscriber_name=subscriber_name,
                status=status,
            ).inc()

            logger.info(
                "event_subscription_registered",
                subscriber_name=subscriber_name,
                event_type_pattern=event_type_pattern,
            )

        except Exception as e:
            status = "failed"
            # Check if it's a database error (table doesn't exist, etc.)
            error_str = str(e)
            is_db_error = (
                "relation" in error_str.lower()
                or "does not exist" in error_str.lower()
                or "connection refused" in error_str.lower()
                or "ProgrammingError" in str(type(e).__name__)
                or "OperationalError" in str(type(e).__name__)
            )
            is_async_error = (
                "async context" in error_str.lower()
                or "sync_to_async" in error_str.lower()
                or "async_to_sync" in error_str.lower()
                or "cannot call this from an async context" in error_str.lower()
            )

            if is_db_error or is_async_error:
                # Database not ready (migrations not applied yet) or async context issue - this is OK
                logger.debug(
                    "event_subscribe_deferred",
                    subscriber_name=subscriber_name,
                    event_type_pattern=event_type_pattern,
                    reason="database_not_ready" if is_db_error else "async_context",
                    error_type=type(e).__name__,
                )
                # Don't raise - registration will happen later when migrations are applied or in sync context
                return

            # Record failure metric
            event_subscriptions_registered_total.labels(
                event_type_pattern=event_type_pattern,
                subscriber_name=subscriber_name,
                status=status,
            ).inc()

            # Other errors should be raised
            logger.error(
                "event_subscribe_error",
                subscriber_name=subscriber_name,
                event_type_pattern=event_type_pattern,
                error=str(e),
                exc_info=True,
            )
            raise EventSubscribeError(f"Failed to subscribe: {e}") from e

    def start_listening(
        self, subscriber_name: str, handler: Callable[[dict[str, Any]], None]
    ) -> None:
        """
        Start listening for events for a subscriber.

        This is a blocking call and should be run in a background thread/worker.

        Args:
            subscriber_name: Subscriber identifier
            handler: Event handler function
        """
        try:
            # Get active subscriptions for this subscriber
            subscriptions = EventSubscription.objects.filter(
                subscriber_name=subscriber_name, is_active=True
            )

            if not subscriptions.exists():
                logger.warning("no_active_subscriptions", subscriber_name=subscriber_name)
                return

            # Create pubsub and subscribe to all channels
            pubsub = self.redis_client.pubsub()
            channels = []
            for subscription in subscriptions:
                # Convert pattern to Redis pattern format
                pattern = subscription.event_type_pattern
                if "*" in pattern:
                    # Use pattern subscribe for wildcards
                    redis_pattern = self._get_channel(pattern).replace("*", "*")
                    pubsub.psubscribe(redis_pattern)
                else:
                    # Use regular subscribe for exact matches
                    channel = self._get_channel(pattern)
                    pubsub.subscribe(channel)
                channels.append(self._get_channel(pattern))

            logger.info(
                "event_listening_started", subscriber_name=subscriber_name, channels=channels
            )

            # Start listening (blocking)
            self._listen(pubsub, subscriber_name, handler)

        except Exception as e:
            logger.error(
                "event_listening_error",
                subscriber_name=subscriber_name,
                error=str(e),
                exc_info=True,
            )
            raise EventSubscribeError(f"Failed to start listening: {e}") from e

    def _listen(
        self,
        pubsub: redis.client.PubSub,
        subscriber_name: str,
        handler: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Listen for events and call handler.

        Args:
            pubsub: Redis PubSub object
            subscriber_name: Subscriber identifier
            handler: Event handler function
        """
        for message in pubsub.listen():
            if message["type"] in ("message", "pmessage"):
                try:
                    event = json.loads(message["data"])
                    event_id = event.get("event_id")
                    event_type = event.get("event_type", "")

                    # Check if event matches subscription pattern
                    if self._matches_pattern(subscriber_name, event_type):
                        # Mark event as pending (for acknowledgment tracking)
                        if event_id:
                            mark_event_pending(
                                event_id,
                                subscriber_name,
                                event_type,
                                redis_client=self.redis_client,
                            )

                            # Increment queue depth when event is marked pending
                            tenant_id = event.get("source", {}).get("tenant_id")
                            tenant_label = get_tenant_id(tenant_id)
                            try:
                                event_queue_depth.labels(
                                    event_type=event_type,
                                    subscriber_name=subscriber_name,
                                    tenant_id=tenant_label,
                                ).inc()
                            except Exception:
                                pass  # Fail silently if metric update fails

                        self._handle_event(subscriber_name, event, handler)
                except json.JSONDecodeError as e:
                    logger.error(
                        "event_decode_error",
                        subscriber_name=subscriber_name,
                        error=str(e),
                    )
                    # Send unparseable message to DLQ so it is not
                    # silently lost.  Build a synthetic event dict
                    # from the raw data so _send_to_dlq can persist it.
                    try:
                        raw = message.get("data", b"")
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8", errors="replace")
                        self._send_to_dlq(
                            subscriber_name,
                            {
                                "event_type": "UNPARSEABLE",
                                "raw_data": raw[:4096],
                            },
                            f"JSON decode error: {e}",
                        )
                    except Exception:
                        pass
                except Exception as e:
                    logger.error(
                        "event_handler_error",
                        subscriber_name=subscriber_name,
                        error=str(e),
                        exc_info=True,
                    )
                    # Send to dead letter queue
                    try:
                        event = json.loads(message["data"])
                        self._send_to_dlq(subscriber_name, event, str(e))
                    except:
                        pass

    def _matches_pattern(self, subscriber_name: str, event_type: str) -> bool:
        """
        Check if event type matches any subscription pattern for subscriber.

        Args:
            subscriber_name: Subscriber identifier
            event_type: Event type to check

        Returns:
            True if matches, False otherwise
        """
        try:
            subscriptions = EventSubscription.objects.filter(
                subscriber_name=subscriber_name, is_active=True
            )

            for subscription in subscriptions:
                pattern = subscription.event_type_pattern
                # Simple wildcard matching (supports * at end)
                if pattern.endswith("*"):
                    prefix = pattern[:-1]
                    if event_type.startswith(prefix):
                        return True
                elif pattern == event_type:
                    return True

            return False
        except Exception:
            # If database query fails, return False (fail closed)
            return False

    def _handle_event(
        self,
        subscriber_name: str,
        event: dict[str, Any],
        handler: Callable[[dict[str, Any]], None],
        retry_count: int = 0,
    ) -> None:
        """Handle event with iterative retry (Phase 93: replaces recursive call).

        Args:
            subscriber_name: Subscriber identifier
            event: Event dictionary
            handler: Event handler function
            retry_count: Initial retry count
        """
        event_type = event.get("event_type", "unknown")
        tenant_id = event.get("source", {}).get("tenant_id")
        tenant_label = get_tenant_id(tenant_id)
        event_id = event.get("event_id")
        event_data = event.get("data", {})

        # Mark event as processing (for acknowledgment tracking)
        if event_id:
            mark_event_processing(event_id, subscriber_name, redis_client=self.redis_client)

        # Check deduplication before processing
        deduplication_key = generate_deduplication_key(event_type, event_data)
        is_duplicate, existing_event_id = check_event_duplicate(
            deduplication_key, redis_client=self.redis_client
        )

        if is_duplicate:
            # Event already processed - skip handling
            logger.info(
                "event_duplicate_skipped",
                subscriber_name=subscriber_name,
                event_id=event_id,
                event_type=event_type,
                existing_event_id=existing_event_id,
                deduplication_key=deduplication_key,
                message=f"Event {event_id} already processed (existing: {existing_event_id}), skipping",
            )

            # Record metrics for skipped duplicate
            event_consumed_total.labels(
                event_type=event_type,
                subscriber_name=subscriber_name,
                status="duplicate_skipped",
                tenant_id=tenant_label,
            ).inc()

            return  # Skip processing duplicate event

        # Create tracing span
        span = None
        if _tracer:
            span = _tracer.start_span(
                name="event_bus.handle",
                attributes={
                    "event.type": event_type,
                    "event.id": event_id or "unknown",
                    "event.subscriber": subscriber_name,
                    "event.tenant_id": tenant_label,
                    "event.retry_count": retry_count,
                },
            )
            # Set parent span context from event if available
            metadata = event.get("metadata", {})
            correlation_id = metadata.get("correlation_id") if metadata else None
            if correlation_id and _trace_available:
                # Try to extract trace context from event metadata
                metadata = event.get("metadata", {})
                if "traceparent" in metadata:
                    try:
                        from opentelemetry.trace.propagation.tracecontext import (
                            TraceContextTextMapPropagator,
                        )

                        carrier = {"traceparent": metadata["traceparent"]}
                        ctx = TraceContextTextMapPropagator().extract(carrier)
                        if ctx:
                            span.set_parent(ctx)
                    except Exception:
                        pass

        # Determine max retries from retry policy
        retry_policy = get_retry_policy(event_type)
        max_retries = getattr(retry_policy, "max_retries", 3)

        for attempt in range(retry_count, max_retries + 1):
            start_time = time.time()
            status = "success"
            try:
                # Calculate event latency (publish to consume time)
                event_timestamp_str = event.get("timestamp")
                if event_timestamp_str:
                    try:
                        from datetime import datetime

                        # Parse event timestamp
                        event_timestamp_str_clean = event_timestamp_str.replace("Z", "+00:00")
                        event_timestamp = datetime.fromisoformat(event_timestamp_str_clean)

                        # Get current time
                        consume_time = timezone.now()

                        # Calculate latency
                        if event_timestamp.tzinfo:
                            # Both timestamps have timezone info
                            latency_seconds = (consume_time - event_timestamp).total_seconds()
                        else:
                            # Fallback: convert to Unix timestamp
                            event_unix = time.mktime(event_timestamp.timetuple())
                            consume_unix = time.time()
                            latency_seconds = consume_unix - event_unix

                        # Record latency metric (only if positive and reasonable)
                        if latency_seconds >= 0 and latency_seconds < 86400:  # Less than 1 day
                            event_latency_seconds.labels(
                                event_type=event_type,
                                subscriber_name=subscriber_name,
                                tenant_id=tenant_label,
                            ).observe(latency_seconds)
                    except Exception as e:
                        logger.debug(
                            "event_latency_calculation_failed", event_id=event_id, error=str(e)
                        )

                handler_timeout = getattr(settings, "EVENT_HANDLER_TIMEOUT_SECONDS", 30)
                _run_with_timeout(handler, args=(event,), timeout_seconds=handler_timeout)
                processing_duration = time.time() - start_time

                # Acknowledge event processing success
                if event_id:
                    acknowledge_event(
                        event_id,
                        subscriber_name,
                        event_type,
                        redis_client=self.redis_client,
                        success=True,
                    )

                    # Decrement queue depth when event is acknowledged
                    try:
                        event_queue_depth.labels(
                            event_type=event_type,
                            subscriber_name=subscriber_name,
                            tenant_id=tenant_label,
                        ).dec()
                    except Exception:
                        pass  # Fail silently if metric update fails

                # Record success metrics
                event_consumed_total.labels(
                    event_type=event_type,
                    subscriber_name=subscriber_name,
                    status=status,
                    tenant_id=tenant_label,
                ).inc()
                event_processing_duration_seconds.labels(
                    event_type=event_type,
                    subscriber_name=subscriber_name,
                    status=status,
                    tenant_id=tenant_label,
                ).observe(processing_duration)

                if attempt > 0:
                    event_handler_retry_count.labels(
                        event_type=event_type,
                        subscriber_name=subscriber_name,
                        tenant_id=tenant_label,
                    ).observe(attempt)

                if span and _trace_available:
                    span.set_attribute("event.processing_duration_seconds", processing_duration)
                    span.set_status(Status(StatusCode.OK))
                    span.end()

                # Store event ID after successful processing for deduplication
                if event_id:
                    store_event_id(deduplication_key, event_id, redis_client=self.redis_client)

                logger.info(
                    "event_handled",
                    subscriber_name=subscriber_name,
                    event_id=event_id,
                    event_type=event_type,
                    deduplication_key=deduplication_key,
                )
                return  # success — exit loop
            except Exception as e:
                processing_duration = time.time() - start_time
                error_type = get_error_type(None, e)
                status = "failed"

                # Record failure metrics
                event_consume_failed_total.labels(
                    event_type=event_type,
                    subscriber_name=subscriber_name,
                    error_type=error_type,
                    tenant_id=tenant_label,
                ).inc()
                event_processing_duration_seconds.labels(
                    event_type=event_type,
                    subscriber_name=subscriber_name,
                    status=status,
                    tenant_id=tenant_label,
                ).observe(processing_duration)

                # Decrement queue depth on failure (event will be retried or sent to DLQ)
                if event_id:
                    try:
                        event_queue_depth.labels(
                            event_type=event_type,
                            subscriber_name=subscriber_name,
                            tenant_id=tenant_label,
                        ).dec()
                    except Exception:
                        pass  # Fail silently if metric update fails

                logger.error(
                    "event_handler_failed",
                    subscriber_name=subscriber_name,
                    event_id=event.get("event_id"),
                    event_type=event_type,
                    retry_count=attempt,
                    error=str(e),
                    exc_info=True,
                )

                # Retry if policy allows
                if retry_policy.should_retry(attempt, e):
                    # Record retry metrics
                    event_handler_retry_count.labels(
                        event_type=event_type,
                        subscriber_name=subscriber_name,
                        tenant_id=tenant_label,
                    ).observe(attempt)

                    # Increment retry attempts counter
                    event_retry_attempts_total.labels(
                        event_type=event_type,
                        subscriber_name=subscriber_name,
                        tenant_id=tenant_label,
                    ).inc()

                    # Increment queue depth for retry
                    try:
                        event_queue_depth.labels(
                            event_type=event_type,
                            subscriber_name=subscriber_name,
                            tenant_id=tenant_label,
                        ).inc()
                    except Exception:
                        pass  # Fail silently if metric update fails

                    # Calculate delay using retry policy
                    delay = retry_policy.calculate_delay(attempt)
                    time.sleep(delay)

                    if span and _trace_available:
                        span.set_attribute("event.retrying", True)
                        span.set_attribute("event.retry_count", attempt + 1)
                        span.set_attribute("event.retry_delay", delay)

                    continue  # next iteration instead of recursion
                else:
                    # Acknowledge event processing failure
                    if event_id:
                        acknowledge_event(
                            event_id,
                            subscriber_name,
                            event_type,
                            redis_client=self.redis_client,
                            success=False,
                        )

                    if span and _trace_available:
                        span.set_attribute("event.sent_to_dlq", True)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        span.end()

                    # Send to dead letter queue
                    self._send_to_dlq(subscriber_name, event, str(e), attempt)
                    return

    def _send_to_dlq(
        self,
        subscriber_name: str,
        event: dict[str, Any],
        error_message: str,
        retry_count: int = 0,
        error_details: dict[str, Any] | None = None,
    ) -> None:
        """
        Send failed event to dead letter queue.

        Args:
            subscriber_name: Subscriber identifier
            event: Event dictionary
            error_message: Error message
            retry_count: Number of retries attempted
            error_details: Additional error details
        """
        event_type = event.get("event_type", "unknown")
        tenant_id = event.get("source", {}).get("tenant_id")
        tenant_label = get_tenant_id(tenant_id)
        error_type = get_error_type(error_details)

        try:
            DeadLetterQueue.objects.create(
                event=event,
                event_type=event_type,
                subscriber=subscriber_name,
                error_message=error_message,
                error_details=error_details or {},
                retry_count=retry_count,
            )

            # Update DLQ metrics
            event_dlq_events_total.labels(
                event_type=event_type,
                subscriber_name=subscriber_name,
                error_type=error_type,
                tenant_id=tenant_label,
            ).inc()
            event_dlq_size.labels(
                event_type=event_type, subscriber_name=subscriber_name, tenant_id=tenant_label
            ).inc()

            # Decrement queue depth when event is sent to DLQ
            try:
                event_queue_depth.labels(
                    event_type=event_type, subscriber_name=subscriber_name, tenant_id=tenant_label
                ).dec()
            except Exception:
                pass  # Fail silently if metric update fails

            logger.warning(
                "event_sent_to_dlq",
                subscriber_name=subscriber_name,
                event_id=event.get("event_id"),
                event_type=event_type,
                retry_count=retry_count,
            )
        except Exception as e:
            logger.error(
                "dlq_error",
                subscriber_name=subscriber_name,
                event_id=event.get("event_id"),
                error=str(e),
                exc_info=True,
            )

    def replay_events(
        self,
        event_type: str | None = None,
        tenant_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Replay events from persistence store.

        Args:
            event_type: Filter by event type (optional)
            tenant_id: Filter by tenant ID (optional)
            start_time: Start time for replay (optional)
            end_time: End time for replay (optional)
            limit: Maximum number of events to replay

        Returns:
            List of event dictionaries
        """
        try:
            queryset = Event.objects.all()

            if event_type:
                queryset = queryset.filter(event_type=event_type)

            if tenant_id:
                queryset = queryset.filter(tenant_id=tenant_id)

            if start_time:
                queryset = queryset.filter(timestamp__gte=start_time)

            if end_time:
                queryset = queryset.filter(timestamp__lte=end_time)

            events = queryset.order_by("timestamp")[:limit]

            result = []
            for event_obj in events:
                event = {
                    "event_id": str(event_obj.event_id),
                    "event_type": event_obj.event_type,
                    "event_version": event_obj.event_version,
                    "timestamp": event_obj.timestamp.isoformat() + "Z",
                    "source": {
                        "service": event_obj.source_service,
                        "tenant_id": str(event_obj.tenant_id) if event_obj.tenant_id else None,
                    },
                    "data": event_obj.data,
                    "metadata": event_obj.metadata or {},
                }

                if event_obj.user_id:
                    event["source"]["user_id"] = str(event_obj.user_id)

                if event_obj.request_id:
                    event["source"]["request_id"] = event_obj.request_id

                result.append(event)

            logger.info(
                "events_replayed", count=len(result), event_type=event_type, tenant_id=tenant_id
            )

            return result

        except Exception as e:
            logger.error("event_replay_error", error=str(e), exc_info=True)
            raise EventBusError(f"Failed to replay events: {e}") from e

    def cleanup_acknowledgment_timeouts(self, subscriber_name: str) -> int:
        """
        Clean up timed-out events for a subscriber.

        Args:
            subscriber_name: Subscriber identifier

        Returns:
            Number of events cleaned up
        """
        return cleanup_timeout_events(subscriber_name, redis_client=self.redis_client)

    def _get_channel(self, event_type: str) -> str:
        """
        Get Redis channel name for event type.

        Args:
            event_type: Event type or pattern

        Returns:
            Channel name
        """
        # Replace dots with colons for Redis channel naming
        channel_name = event_type.replace(".", ":")
        return f"{self.channel_prefix}:{channel_name}"


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get global event bus instance."""
    global _event_bus
    if _event_bus is None:
        force_sync = getattr(settings, "EVENT_BUS_FORCE_SYNC_PERSISTENCE", False)
        _event_bus = EventBus(force_sync_persistence=force_sync)
    return _event_bus
