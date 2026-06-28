"""
Event Publishers

Convenience classes for publishing events from services.
"""
from typing import Dict, Any, Optional, List
from functools import wraps
import structlog

from .bus import get_event_bus, EventBusError
from .deduplication import (
    generate_deduplication_key,
    check_event_duplicate,
    store_event_id,
    DEFAULT_DEDUPLICATION_TTL,
)

logger = structlog.get_logger(__name__)


class EventPublisher:
    """
    Base event publisher class.

    Provides convenient methods for publishing events from services.
    """

    def __init__(self, service_name: str, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize event publisher.

        Args:
            service_name: Name of the service publishing events
            tenant_id: Default tenant ID (can be overridden per event)
            user_id: Default user ID (can be overridden per event)
        """
        self.service_name = service_name
        self.default_tenant_id = tenant_id
        self.default_user_id = user_id
        self._event_bus = None  # lazy — deferred until first publish()

    @property
    def event_bus(self):
        """Lazy singleton accessor — EventBus is created on first use, not at init.

        This prevents service constructors (e.g. MarketplaceIntegrationService)
        from triggering Redis connection during import / LiveServer thread start.
        """
        if self._event_bus is None:
            self._event_bus = get_event_bus()
        return self._event_bus

    @event_bus.setter
    def event_bus(self, value):
        """Allow tests to inject a mock/stub event bus."""
        self._event_bus = value

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
        skip_deduplication: bool = False
    ) -> str:
        """
        Publish an event with deduplication support.

        Args:
            event_type: Event type (e.g., 'contract.created')
            data: Event data payload
            tenant_id: Tenant ID (uses default if not provided)
            user_id: User ID (uses default if not provided)
            request_id: Request ID for tracing
            correlation_id: Correlation ID for tracing
            causation_id: Event ID that caused this event
            tags: Tags for filtering
            skip_deduplication: If True, skip deduplication check (default: False)

        Returns:
            Event ID (existing event ID if duplicate, new event ID if not)
        """
        # Check for duplicate before publishing (unless explicitly skipped)
        if not skip_deduplication:
            try:
                deduplication_key = generate_deduplication_key(event_type, data)
                is_duplicate, existing_event_id = check_event_duplicate(deduplication_key)

                if is_duplicate and existing_event_id:
                    logger.debug(
                        "event_publish_duplicate_skipped",
                        service=self.service_name,
                        event_type=event_type,
                        existing_event_id=existing_event_id,
                        deduplication_key=deduplication_key
                    )
                    # Return existing event ID (deduplicated)
                    return existing_event_id
            except (ValueError, TypeError) as dedup_error:
                # Only ValueError/TypeError — the only realistic failures
                # from generate_deduplication_key (bad data /
                # non-hashable payload). check_event_duplicate has its
                # own internal Redis-error catch and never raises.
                # Continue with publish (fail open).
                logger.warning(
                    "event_deduplication_check_failed",
                    service=self.service_name,
                    event_type=event_type,
                    error=str(dedup_error),
                    message="Continuing with publish despite deduplication check failure"
                )

        try:
            # Publish event
            event_id = self.event_bus.publish(
                event_type=event_type,
                data=data,
                tenant_id=tenant_id or self.default_tenant_id,
                user_id=user_id or self.default_user_id,
                request_id=request_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                tags=tags,
                service_name=self.service_name
            )

            # Store event ID for deduplication after successful publish
            if not skip_deduplication:
                try:
                    deduplication_key = generate_deduplication_key(event_type, data)
                    store_event_id(
                        deduplication_key,
                        event_id,
                        ttl=DEFAULT_DEDUPLICATION_TTL
                    )
                except (ValueError, TypeError) as store_error:
                    # Only ValueError/TypeError — the only realistic
                    # failures from generate_deduplication_key.
                    # store_event_id has its own internal Redis-error
                    # catch and never raises. Fail open.
                    logger.warning(
                        "event_deduplication_store_failed",
                        service=self.service_name,
                        event_type=event_type,
                        event_id=event_id,
                        error=str(store_error),
                        message="Event published but deduplication storage failed"
                    )

            return event_id
        except EventBusError as e:
            logger.error(
                "event_publish_failed",
                service=self.service_name,
                event_type=event_type,
                error=str(e)
            )
            raise


def publish_event(
    event_type: str,
    data: Dict[str, Any],
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    skip_deduplication: bool = False,
    **kwargs
) -> str:
    """
    Convenience function to publish an event with deduplication support.

    Args:
        event_type: Event type
        data: Event data
        tenant_id: Tenant ID
        user_id: User ID
        skip_deduplication: If True, skip deduplication check (default: False)
        **kwargs: Additional event parameters

    Returns:
        Event ID (existing event ID if duplicate, new event ID if not)
    """
    publisher = EventPublisher(service_name="hub", tenant_id=tenant_id, user_id=user_id)
    return publisher.publish(
        event_type,
        data,
        skip_deduplication=skip_deduplication,
        **kwargs
    )


def event_publisher(event_type: str, **default_kwargs):
    """
    Decorator to automatically publish events after function execution.

    Usage:
        @event_publisher('contract.created', tenant_id='...')
        def create_contract(...):
            ...
            return contract_id

    Args:
        event_type: Event type to publish
        **default_kwargs: Default event parameters
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Extract event data from result
            if isinstance(result, dict):
                data = result
            else:
                # Try to extract from function result
                data = {"result": str(result)}

            # Publish event
            try:
                publish_event(event_type, data, **default_kwargs)
            except EventBusError as e:
                logger.error(
                    "decorator_event_publish_failed",
                    event_type=event_type,
                    function=func.__name__,
                    error=str(e)
                )

            return result
        return wrapper
    return decorator

