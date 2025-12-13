# Event Bus Documentation

## Overview

The Event Bus provides event-driven communication infrastructure for the Data Interoperability Hub. It enables decoupled, asynchronous communication between services using Redis Pub/Sub for real-time delivery and PostgreSQL for persistence, replay, and audit.

## Architecture

### Components

1. **Event Bus** (`hub/apps/core/events/bus.py`)
   - Redis Pub/Sub for real-time event delivery
   - PostgreSQL for event persistence
   - Dead letter queue for failed events
   - Event replay functionality

2. **Event Schema** (`hub/apps/core/events/schema.py`)
   - JSON Schema validation
   - Event building utilities
   - Type-specific schemas

3. **Event Publishers** (`hub/apps/core/events/publisher.py`)
   - Convenience classes for publishing events
   - Decorator support for automatic event publishing

4. **Event Subscribers** (`hub/apps/core/events/subscriber.py`)
   - Subscription management
   - Handler wrapping with error handling
   - Transaction management

5. **Event Models** (`hub/apps/core/events/models.py`)
   - `Event`: Event persistence
   - `DeadLetterQueue`: Failed event storage
   - `EventSubscription`: Subscription tracking

## Event Schema

### Base Event Structure

```json
{
  "event_id": "uuid",
  "event_type": "contract.created",
  "event_version": "1.0.0",
  "timestamp": "2025-01-15T10:00:00Z",
  "source": {
    "service": "hub",
    "tenant_id": "uuid",
    "user_id": "uuid",
    "request_id": "request-id"
  },
  "data": {
    "contract_id": "uuid"
  },
  "metadata": {
    "correlation_id": "correlation-id",
    "causation_id": "uuid",
    "tags": ["tag1", "tag2"]
  }
}
```

### Event Type Format

Event types follow the pattern: `domain.entity.action` (e.g., `contract.created`, `asset.activated`).

## Usage

### Publishing Events

#### Using EventPublisher

```python
from hub.apps.core.events import EventPublisher

publisher = EventPublisher(
    service_name="contract_service",
    tenant_id=tenant_id,
    user_id=user_id
)

event_id = publisher.publish(
    event_type="contract.created",
    data={
        "contract_id": str(contract.id),
        "asset_id": str(asset.id)
    },
    correlation_id=correlation_id
)
```

#### Using publish_event Function

```python
from hub.apps.core.events import publish_event

event_id = publish_event(
    event_type="contract.created",
    data={"contract_id": str(contract.id)},
    tenant_id=tenant_id
)
```

#### Using Decorator

```python
from hub.apps.core.events import event_publisher

@event_publisher('contract.created', tenant_id=tenant_id)
def create_contract(...):
    contract = Contract.objects.create(...)
    return {"contract_id": str(contract.id)}
```

### Subscribing to Events

#### Using EventSubscriber

```python
from hub.apps.core.events import EventSubscriber

def handle_contract_events(event):
    contract_id = event["data"]["contract_id"]
    # Process event
    pass

subscriber = EventSubscriber("webhook_service")
subscriber.subscribe("contract.*", handle_contract_events)
```

#### Using Decorator

```python
from hub.apps.core.events import event_subscriber

@event_subscriber('webhook_service', 'contract.*')
def handle_contract_events(event):
    contract_id = event["data"]["contract_id"]
    # Process event
    pass
```

### Event Replay

```python
from hub.apps.core.events import get_event_bus
from datetime import datetime, timedelta

event_bus = get_event_bus()

# Replay events from last hour
events = event_bus.replay_events(
    event_type="contract.created",
    start_time=datetime.utcnow() - timedelta(hours=1),
    limit=1000
)

# Republish events
for event in events:
    event_bus.publish(**event)
```

### Dead Letter Queue

Failed events are automatically sent to the dead letter queue after max retries.

```python
from hub.apps.core.events.models import DeadLetterQueue

# Get failed events
failed_events = DeadLetterQueue.objects.filter(
    subscriber="webhook_service",
    resolved_at__isnull=True
)

# Resolve failed event
dlq_entry.resolved_at = timezone.now()
dlq_entry.resolved_by = user_id
dlq_entry.save()
```

## Configuration

### Settings

```python
# Redis URL
REDIS_URL = 'redis://localhost:6379/0'

# Event bus settings
EVENT_BUS_CHANNEL_PREFIX = 'events'
EVENT_BUS_ENABLE_PERSISTENCE = True
EVENT_BUS_MAX_RETRIES = 3
```

## Event Types

### Contract Events
- `contract.created`
- `contract.updated`
- `contract.deleted`
- `contract.validated`
- `contract.normalized`

### Asset Events
- `asset.created`
- `asset.updated`
- `asset.activated`
- `asset.published`
- `asset.retired`

### Dataset Events
- `dataset.created`
- `dataset.updated`
- `dataset.deleted`
- `dataset.uploaded`

### Workflow Events
- `workflow.started`
- `workflow.completed`
- `workflow.failed`
- `workflow.cancelled`
- `workflow.step.completed`
- `workflow.step.failed`

See `openspec/changes/backendready/tasks.md` for complete list of event types.

## Best Practices

1. **Event Naming**: Use consistent naming convention (`domain.entity.action`)
2. **Event Versioning**: Include schema version for backward compatibility
3. **Error Handling**: Always handle event publishing errors gracefully
4. **Idempotency**: Make event handlers idempotent
5. **Transaction Management**: Use transactions for event handlers
6. **Monitoring**: Monitor dead letter queue regularly
7. **Replay Safety**: Ensure replay handlers are idempotent

## Testing

See `hub/apps/core/events/tests/` for comprehensive test examples.

## Migration

Run migrations to create event tables:

```bash
python manage.py migrate events
```

## Performance Considerations

- Redis Pub/Sub provides low-latency event delivery
- PostgreSQL persistence adds minimal overhead (<5ms per event)
- Event replay queries are optimized with indexes
- Dead letter queue queries use indexes for fast lookups

## Troubleshooting

### Events Not Being Received

1. Check Redis connection
2. Verify subscription is active
3. Check event type pattern matching
4. Review dead letter queue for failures

### High Dead Letter Queue Volume

1. Review error messages
2. Check handler implementation
3. Verify event schema compatibility
4. Review retry configuration

### Performance Issues

1. Monitor Redis connection pool
2. Review PostgreSQL indexes
3. Consider event batching for high-volume scenarios
4. Monitor event persistence latency

