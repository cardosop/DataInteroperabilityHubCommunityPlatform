"""
Event Bus Module

Provides event-driven communication infrastructure with Redis Pub/Sub and PostgreSQL persistence.
"""

from .bus import EventBus, EventBusError, EventPublishError, EventSubscribeError, get_event_bus
from .event_types import (
    CURRENT_EVENT_VERSION,
    EVENT_TYPE_SCHEMAS,
    get_all_event_types,
    get_event_schema,
    validate_event_data,
)
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
from .deduplication import (
    generate_deduplication_key,
    check_event_duplicate,
    store_event_id,
    is_event_duplicate,
    get_redis_client as get_deduplication_redis_client,
    DEFAULT_DEDUPLICATION_TTL,
    DEDUPLICATION_KEY_PREFIX,
)

__all__ = [
    # Bus
    "EventBus",
    "get_event_bus",
    "EventBusError",
    "EventPublishError",
    "EventSubscribeError",
    # Schema
    "EventSchema",
    "BASE_EVENT_SCHEMA",
    "get_event_schema",
    # Publisher
    "EventPublisher",
    "publish_event",
    "event_publisher",
    # Subscriber
    "EventSubscriber",
    "event_subscriber",
    # Models
    "Event",
    "DeadLetterQueue",
    "EventSubscription",
    # Deduplication
    "generate_deduplication_key",
    "check_event_duplicate",
    "store_event_id",
    "is_event_duplicate",
    "get_deduplication_redis_client",
    "DEFAULT_DEDUPLICATION_TTL",
    "DEDUPLICATION_KEY_PREFIX",
]
