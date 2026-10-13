"""
Event Bus Module

Provides event-driven communication infrastructure with Redis Pub/Sub and PostgreSQL persistence.
"""

from .bus import EventBus, EventBusError, EventPublishError, EventSubscribeError, get_event_bus
from .deduplication import (
    CONSUMER_DEDUP_NAMESPACE,
    DEDUPLICATION_KEY_PREFIX,
    DEFAULT_DEDUP_NAMESPACE,
    DEFAULT_DEDUPLICATION_TTL,
    PUBLISHER_DEDUP_NAMESPACE,
    check_event_duplicate,
    clear_all_dedup_namespaces,
    generate_deduplication_key,
    is_event_duplicate,
    store_event_id,
)
from .deduplication import (
    get_redis_client as get_deduplication_redis_client,
)
from .event_types import (
    CURRENT_EVENT_VERSION,
    EVENT_TYPE_SCHEMAS,
    get_all_event_types,
    validate_event_data,
)
from .listener import EventBusListener, start_event_listener, stop_event_listener
from .models import DeadLetterQueue, Event, EventSubscription
from .publisher import EventPublisher, event_publisher, publish_event
from .schema import BASE_EVENT_SCHEMA, EventSchema, get_event_schema
from .subscriber import EventSubscriber, event_subscriber
from .subscribers import (
    NotificationSubscriber,
    WebhookSubscriber,
    WorkflowStepSubscriber,
    WorkflowTriggerSubscriber,
)
from .versioning import EventSchemaVersionManager, get_version_manager

__all__ = [
    "BASE_EVENT_SCHEMA",
    "CONSUMER_DEDUP_NAMESPACE",
    "DEDUPLICATION_KEY_PREFIX",
    "DEFAULT_DEDUPLICATION_TTL",
    "DEFAULT_DEDUP_NAMESPACE",
    "PUBLISHER_DEDUP_NAMESPACE",
    "DeadLetterQueue",
    "Event",
    "EventBus",
    "EventBusError",
    "EventBusListener",
    "EventPublishError",
    "EventPublisher",
    "EventSchema",
    "EventSubscribeError",
    "EventSubscriber",
    "EventSubscription",
    "check_event_duplicate",
    "clear_all_dedup_namespaces",
    "event_publisher",
    "event_subscriber",
    "generate_deduplication_key",
    "get_deduplication_redis_client",
    "get_event_bus",
    "get_event_schema",
    "is_event_duplicate",
    "publish_event",
    "start_event_listener",
    "stop_event_listener",
    "store_event_id",
]
