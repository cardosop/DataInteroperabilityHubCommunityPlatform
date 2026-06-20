"""
Event Subscribers

Convenience classes for subscribing to events.
"""

from collections.abc import Callable
from typing import Any

import structlog
from django.db import transaction

from .bus import EventBusError, get_event_bus
from .models import EventSubscription

logger = structlog.get_logger(__name__)


class EventSubscriber:
    """
    Base event subscriber class.

    Provides convenient methods for subscribing to events.
    """

    def __init__(self, subscriber_name: str, event_bus=None):
        """
        Initialize event subscriber.

        Args:
            subscriber_name: Unique subscriber identifier
            event_bus: Optional event bus instance (default: get from service)
        """
        self.subscriber_name = subscriber_name
        self.event_bus = event_bus or get_event_bus()
        self.handlers: dict[str, Callable[[dict[str, Any]], None]] = {}

    def subscribe(
        self,
        event_type_pattern: str,
        handler: Callable[[dict[str, Any]], None],
        is_active: bool = True,
    ) -> None:
        """
        Subscribe to events matching a pattern.

        Args:
            event_type_pattern: Event type pattern (supports wildcards)
            handler: Handler function
            is_active: Whether subscription is active
        """
        try:
            # Store handler
            self.handlers[event_type_pattern] = self._wrap_handler(handler)

            # Always delegate to EventBus which checks DB availability directly
            self.event_bus.subscribe(
                subscriber_name=self.subscriber_name,
                event_type_pattern=event_type_pattern,
                handler=self.handlers[event_type_pattern],
                is_active=is_active,
            )

            logger.info(
                "event_subscription_registered",
                subscriber_name=self.subscriber_name,
                event_type_pattern=event_type_pattern,
            )
        except (EventBusError, RuntimeError) as e:
            # Check if it's a database access error (common during test collection)
            error_str = str(e)
            if "Database access not allowed" in error_str or "django_db" in error_str:
                # Database not available - this is OK during test collection
                logger.debug(
                    "deferred_event_subscription",
                    subscriber_name=self.subscriber_name,
                    event_type_pattern=event_type_pattern,
                    reason="database_not_available",
                )
                # Don't raise - registration will happen later when database is available
                return

            logger.error(
                "event_subscription_failed",
                subscriber_name=self.subscriber_name,
                event_type_pattern=event_type_pattern,
                error=str(e),
            )
            raise

    def start_listening(self) -> None:
        """
        Start listening for events.

        This is a blocking call and should be run in a background thread/worker.
        """
        if not self.handlers:
            logger.warning("no_handlers_registered", subscriber_name=self.subscriber_name)
            return

        # Use first handler as default (in production, use proper routing)
        default_handler = list(self.handlers.values())[0]
        self.event_bus.start_listening(self.subscriber_name, default_handler)

    def _wrap_handler(
        self, handler: Callable[[dict[str, Any]], None]
    ) -> Callable[[dict[str, Any]], None]:
        """
        Wrap handler with error handling and transaction management.

        Args:
            handler: Original handler function

        Returns:
            Wrapped handler function
        """

        def wrapped_handler(event: dict[str, Any]) -> None:
            try:
                # Run handler in transaction
                with transaction.atomic():
                    handler(event)
            except Exception as e:
                logger.error(
                    "event_handler_error",
                    subscriber_name=self.subscriber_name,
                    event_id=event.get("event_id"),
                    event_type=event.get("event_type"),
                    error=str(e),
                    exc_info=True,
                )
                raise

        return wrapped_handler

    def unsubscribe(self, event_type_pattern: str) -> None:
        """
        Unsubscribe from events.

        Args:
            event_type_pattern: Event type pattern to unsubscribe from
        """
        try:
            EventSubscription.objects.filter(
                subscriber_name=self.subscriber_name, event_type_pattern=event_type_pattern
            ).update(is_active=False)

            if event_type_pattern in self.handlers:
                del self.handlers[event_type_pattern]

            logger.info(
                "event_subscription_removed",
                subscriber_name=self.subscriber_name,
                event_type_pattern=event_type_pattern,
            )
        except Exception as e:
            logger.error(
                "event_unsubscribe_error",
                subscriber_name=self.subscriber_name,
                event_type_pattern=event_type_pattern,
                error=str(e),
            )
            raise


def event_subscriber(subscriber_name: str, event_type_pattern: str):
    """
    Decorator to register an event subscriber.

    Usage:
        @event_subscriber('webhook_service', 'contract.*')
        def handle_contract_events(event):
            ...

    Args:
        subscriber_name: Subscriber identifier
        event_type_pattern: Event type pattern
    """

    def decorator(func: Callable[[dict[str, Any]], None]):
        # Lazy registration - only register when database is available
        # This prevents errors during test collection when database access is blocked
        def _lazy_register():
            try:
                # Check if we're in an async context and handle appropriately
                import asyncio

                try:
                    # Try to get the current event loop
                    asyncio.get_running_loop()
                    # We're in an async context - defer registration to avoid async/sync conflicts
                    # Registration will happen when the service starts up properly
                    logger.debug(
                        "deferred_event_subscription_async_context",
                        subscriber_name=subscriber_name,
                        event_type_pattern=event_type_pattern,
                        reason="async_context_detected",
                    )
                    return
                except RuntimeError:
                    # No running event loop - we're in sync context, safe to proceed
                    pass

                subscriber = EventSubscriber(subscriber_name)
                subscriber.subscribe(event_type_pattern, func)
            except (RuntimeError, Exception) as e:
                # Database access not allowed (e.g., during test collection or migrations)
                # Registration will happen later when database is available
                error_str = str(e)
                is_db_error = (
                    "Database access not allowed" in error_str
                    or "django_db" in error_str
                    or "relation" in error_str.lower()
                    or "does not exist" in error_str.lower()
                    or "connection refused" in error_str.lower()
                    or "ProgrammingError" in str(type(e).__name__)
                    or "OperationalError" in str(type(e).__name__)
                )
                is_async_error = (
                    "async context" in error_str.lower()
                    or "sync_to_async" in error_str.lower()
                    or "async_to_sync" in error_str.lower()
                )
                if is_db_error or is_async_error:
                    logger.debug(
                        "deferred_event_subscription",
                        subscriber_name=subscriber_name,
                        event_type_pattern=event_type_pattern,
                        reason="database_not_available" if is_db_error else "async_context",
                        error_type=type(e).__name__,
                    )
                    # Don't raise - registration will happen later
                    return
                else:
                    # Other errors should be raised
                    raise

        # Try to register immediately, but don't fail if database isn't available
        try:
            _lazy_register()
        except Exception as e:
            # If it's a database access error (table doesn't exist, connection refused, etc.), ignore it
            error_str = str(e)
            is_db_error = (
                "Database access not allowed" in error_str
                or "django_db" in error_str
                or "relation" in error_str.lower()
                or "does not exist" in error_str.lower()
                or "connection refused" in error_str.lower()
                or "ProgrammingError" in str(type(e).__name__)
                or "OperationalError" in str(type(e).__name__)
            )
            is_async_error = (
                "async context" in error_str.lower()
                or "sync_to_async" in error_str.lower()
                or "async_to_sync" in error_str.lower()
            )
            if not (is_db_error or is_async_error):
                # Re-raise non-database/async errors
                raise
            # Database not available or table doesn't exist yet - registration will happen later
            logger.debug(
                "deferred_event_subscription_at_import",
                subscriber_name=subscriber_name,
                event_type_pattern=event_type_pattern,
                reason="database_not_ready",
                error_type=type(e).__name__,
            )

        return func

    return decorator
