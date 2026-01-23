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

3. **Event Publishers** (`hub/apps/core/events/publisher.py` and `hub/apps/core/events/service_publishers.py`)
   - Base `EventPublisher` class for direct event publishing
   - Service-specific event publisher mixins (23 publishers)
   - Decorator support for automatic event publishing
   - Event deduplication support

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

Event replay allows administrators to reprocess events that were previously published. This is useful for:
- Recovering from subscriber failures
- Reprocessing events after fixing bugs
- Testing event handlers
- Data recovery scenarios

#### API Endpoint

The event replay API endpoint (`POST /api/v1/events/replay/`) provides programmatic access to replay events.

**Authentication**: Requires `PLATFORM_ADMIN` or `TENANT_ADMIN` role.

**Rate Limiting**: 10 replays per hour per tenant.

**Request Body**:
```json
{
  "event_type": "odps.created",  // Optional: filter by event type
  "tenant_id": "uuid",            // Optional: filter by tenant ID
  "start_time": "2025-01-01T00:00:00Z",  // Optional: start time (ISO 8601)
  "end_time": "2025-01-02T00:00:00Z",    // Optional: end time (ISO 8601)
  "limit": 100                    // Optional: max events (default: 100, max: 1000)
}
```

**Response**:
```json
{
  "success": true,
  "events_replayed": 5,
  "events_skipped": 2,
  "total_events_found": 7,
  "event_ids": ["uuid1", "uuid2", ...],
  "skipped_event_ids": ["uuid3", "uuid4"]
}
```

**Example**:
```bash
curl -X POST https://api.example.com/api/v1/events/replay/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "odps.created",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "start_time": "2025-01-01T00:00:00Z",
    "limit": 100
  }'
```

#### Management Command

The `replay_events` management command provides CLI access to replay events.

**Usage**:
```bash
python manage.py replay_events [options]
```

**Options**:
- `--event-type TYPE`: Filter by event type (e.g., "odps.created")
- `--tenant-id ID`: Filter by tenant ID
- `--start-time TIME`: Start time for replay (ISO 8601 format)
- `--end-time TIME`: End time for replay (ISO 8601 format)
- `--limit N`: Maximum number of events to replay (default: 1000, max: 10000)
- `--dry-run`: Show what would be replayed without actually replaying
- `--batch-size N`: Number of events to process per batch (default: 100)
- `--skip-duplicates`: Skip events that have already been replayed (default: True)

**Examples**:
```bash
# Dry run to see what would be replayed
python manage.py replay_events --event-type odps.created --tenant-id <uuid> --dry-run

# Replay events from last 24 hours
python manage.py replay_events \
  --tenant-id <uuid> \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ) \
  --limit 1000

# Replay specific event type in batches
python manage.py replay_events \
  --event-type odps.created \
  --tenant-id <uuid> \
  --batch-size 50 \
  --limit 500
```

#### Idempotency

Event replay is **idempotent** by default. Events that have already been replayed within the last 24 hours are automatically skipped to prevent duplicate processing.

The idempotency check uses Redis to track replayed events:
- Each replayed event is marked with a key: `event_replay:event_id:<event_id>`
- Keys expire after 24 hours
- If Redis is unavailable, replay continues but duplicate detection is disabled (graceful degradation)

#### Best Practices

1. **Use Dry-Run First**: Always test with `--dry-run` before actual replay
2. **Filter Appropriately**: Use filters (event_type, tenant_id, time range) to limit scope
3. **Batch Processing**: Use `--batch-size` for large replays to avoid memory issues
4. **Monitor Results**: Check the response/command output for skipped events
5. **Idempotent Handlers**: Ensure event handlers are idempotent to handle replays safely
6. **Rate Limits**: Be aware of rate limits (10 replays/hour/tenant) when automating

#### Programmatic Usage

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

## Event Publishers

The Event Bus provides **23 service-specific event publisher mixins** that enable services to publish events in a standardized, type-safe manner. All publishers follow the same pattern and are located in `hub/apps/core/events/service_publishers.py`.

### Event Publisher Pattern

All event publishers follow this consistent pattern:

1. **Mixin Class**: Each publisher is a mixin class that can be added to service classes
2. **Initialization**: Publishers initialize an internal `EventPublisher` instance with service name and tenant/user context
3. **Publish Methods**: Each publisher provides typed `publish_*` methods for specific event types
4. **Deduplication**: All publishers support automatic event deduplication
5. **Error Handling**: Publishers handle errors gracefully with retry logic where appropriate

### Base EventPublisher

The base `EventPublisher` class (`hub/apps/core/events/publisher.py`) provides:

- **Service Context**: Tracks service name, tenant_id, and user_id
- **Publish Method**: Generic `publish()` method with deduplication support
- **Error Handling**: Graceful error handling with logging
- **Deduplication**: Automatic duplicate event detection using Redis

### Service Event Publishers

All service-specific publishers are mixins that extend services with event publishing capabilities:

#### 1. ContractEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `ContractService`
**Events Published**:
- `contract.created` - Contract creation
- `contract.updated` - Contract updates
- `contract.deleted` - Contract deletion
- `contract.validated` - Contract validation completion
- `contract.normalized` - Contract normalization completion

**Usage**:
```python
class ContractService(BaseService, ContractEventPublisher):
    def create_contract(self, ...):
        contract = Contract.objects.create(...)
        self.publish_contract_created(
            contract_id=str(contract.id),
            status="ACTIVE"
        )
        return contract
```

#### 2. AssetEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `AssetService`
**Events Published**:
- `asset.created` - Asset creation
- `asset.updated` - Asset updates
- `asset.activated` - Asset activation
- `asset.published` - Asset published to marketplace
- `asset.retired` - Asset retirement

#### 3. DatasetEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `DatasetService`
**Events Published**:
- `dataset.created` - Dataset creation
- `dataset.updated` - Dataset updates
- `dataset.deleted` - Dataset deletion
- `dataset.uploaded` - Dataset file upload

#### 4. IngestionEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `IngestionService`
**Events Published**:
- `ingestion.started` - Ingestion process started
- `ingestion.completed` - Ingestion process completed
- `ingestion.failed` - Ingestion process failed
- `ingestion.file_processed` - Single file processed during ingestion

#### 5. QualityEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: Quality service
**Events Published**:
- `quality.check.started` - Quality check started
- `quality.check.completed` - Quality check completed
- `quality.check.failed` - Quality check failed
- `quality.anomaly.detected` - Quality anomaly detected

#### 6. ComplianceEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `ComplianceService`
**Events Published**:
- `compliance.check.started` - Compliance check started
- `compliance.check.completed` - Compliance check completed
- `compliance.check.failed` - Compliance check failed
- `compliance.report.generated` - Compliance report generated

#### 7. VersionEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: Versioning service
**Events Published**:
- `version.created` - Version created
- `version.updated` - Version updated
- `version.rolled_back` - Version rolled back

#### 8. VersioningEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `VersioningService`
**Events Published**:
- `version.created` - Version created
- `version.updated` - Version updated
- `version.deleted` - Version deleted
- `version.promoted` - Version promoted

#### 9. AccessEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `GovernanceService`
**Events Published**:
- `access.requested` - Access request created
- `access.granted` - Access granted
- `access.revoked` - Access revoked
- `access.certified` - Access certified

#### 10. MarketplaceEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `MarketplaceService`
**Events Published**:
- `marketplace.listing.published` - Marketplace listing published
- `marketplace.listing.unpublished` - Marketplace listing unpublished
- `marketplace.order.created` - Marketplace order created
- `marketplace.order.approved` - Marketplace order approved
- `marketplace.order.rejected` - Marketplace order rejected
- `marketplace.order.fulfilled` - Marketplace order fulfilled
- `marketplace.entitlement.granted` - Marketplace entitlement granted
- `marketplace.entitlement.revoked` - Marketplace entitlement revoked

#### 11. WorkflowEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `WorkflowEngine`
**Events Published**:
- `workflow.created` - Workflow instance created
- `workflow.started` - Workflow instance started
- `workflow.completed` - Workflow instance completed
- `workflow.failed` - Workflow instance failed
- `workflow.cancelled` - Workflow instance cancelled
- `workflow.step.started` - Workflow step started
- `workflow.step.completed` - Workflow step completed
- `workflow.step.failed` - Workflow step failed

#### 12. ODPSEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `ContractService`, `ODPSService`
**Events Published**:
- `odps.created` - ODPS contract created
- `odps.updated` - ODPS contract updated
- `odps.deleted` - ODPS contract deleted
- `odps.normalized` - ODPS contract normalized
- `odps.linked` - ODPS contract linked to ODCS
- `odps.unlinked` - ODPS contract unlinked from ODCS
- `odps.ref.resolved` - ODPS $ref resolution completed
- `odps.ref.failed` - ODPS $ref resolution failed
- `odps.export.started` - ODPS export started
- `odps.export.completed` - ODPS export completed
- `odps.export.failed` - ODPS export failed
- `odps.workflow.started` - ODPS workflow started
- `odps.workflow.completed` - ODPS workflow completed
- `odps.workflow.failed` - ODPS workflow failed
- `odps.workflow.step.completed` - ODPS workflow step completed
- `odps.workflow.step.failed` - ODPS workflow step failed
- `odps.workflow.progress` - ODPS workflow progress update
- `odps.creation.progress` - ODPS creation progress update
- `odps.normalization.progress` - ODPS normalization progress update
- `odps.ref.progress` - ODPS $ref resolution progress update
- `odps.linking.status` - ODPS linking status update
- `odps.export.progress` - ODPS export progress update
- `odps.semantic.mapping.progress` - ODPS semantic mapping progress update
- `odps.semantic.mapped` - ODPS semantic mapping completed

**Special Features**:
- Retry logic with exponential backoff for transient failures
- Graceful degradation on publish failures
- Progress event publishing for long-running operations

#### 14. DataMeshEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `DataMeshService`
**Events Published**:
- `domain.created` - Data mesh domain created
- `domain.updated` - Data mesh domain updated
- `domain.deleted` - Data mesh domain deleted
- `policy.applied` - Policy applied to domain
- `policy.revoked` - Policy revoked from domain
- `compliance.report.generated` - Compliance report generated
- `mesh.compliance.checked` - Mesh compliance checked
- `mesh.topology.updated` - Mesh topology updated
- `mesh.domain.created` - Mesh domain created (internal)
- `mesh.domain.updated` - Mesh domain updated (internal)
- `mesh.policy.applied` - Mesh policy applied (internal)
- `mesh.compliance.checked` - Mesh compliance checked (internal)
- `mesh.health.status_changed` - Mesh health status changed

**Special Features**:
- Webhook integration for mesh events
- Internal and external event type mapping

#### 15. VirtualizationEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `VirtualizationService`
**Events Published**:
- `virtualization.dataset.created` - Virtual dataset created
- `virtualization.dataset.updated` - Virtual dataset updated
- `virtualization.dataset.deleted` - Virtual dataset deleted
- `virtualization.query.execution.started` - Query execution started
- `virtualization.query.execution.progress` - Query execution progress
- `virtualization.query.execution.completed` - Query execution completed
- `virtualization.query.execution.failed` - Query execution failed
- `virtualization.query.execution.cancelled` - Query execution cancelled

**Special Features**:
- Webhook integration for virtualization events
- Progress event publishing for long-running queries

#### 16. FileEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `FileService`
**Events Published**:
- `file.created` - File created
- `file.updated` - File updated
- `file.deleted` - File deleted
- `file.uploaded` - File uploaded
- `file.downloaded` - File downloaded

#### 17. LineageEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `LineageService`
**Events Published**:
- `lineage.updated` - Lineage updated
- `lineage.relationship_added` - Lineage relationship added
- `lineage.relationship_removed` - Lineage relationship removed

#### 18. SearchEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `SearchService`
**Events Published**:
- `search.query` - Search query executed
- `search.index.updated` - Search index updated
- `search.index.rebuilt` - Search index rebuilt

#### 19. PaymentGatewayEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `PaymentGatewayService`
**Events Published**:
- `payment.gateway.linked` - Payment gateway linked
- `payment.gateway.unlinked` - Payment gateway unlinked
- `payment.gateway.webhook.received` - Payment gateway webhook received

#### 20. TenantEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `TenantService`
**Events Published**:
- `tenant.created` - Tenant created
- `tenant.updated` - Tenant updated
- `tenant.deleted` - Tenant deleted
- `tenant.quota.changed` - Tenant quota changed

#### 21. NormalizationEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `NormalizationService`
**Events Published**:
- `normalization.started` - Normalization started
- `normalization.completed` - Normalization completed
- `normalization.failed` - Normalization failed

#### 22. PaymentEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `PaymentService`
**Events Published**:
- `payment.initiated` - Payment initiated
- `payment.completed` - Payment completed
- `payment.failed` - Payment failed
- `payment.refunded` - Payment refunded

#### 23. ObservabilityEventPublisher
**Location**: `hub/apps/core/events/service_publishers.py`
**Service**: `ObservabilityService`
**Events Published**:
- `observability.metric.recorded` - Metric recorded
- `observability.trace.created` - Trace created
- `observability.log.created` - Log created
- `observability.alert.triggered` - Alert triggered

### Event Publisher Pattern Implementation

#### Creating a Service with Event Publishing

```python
from hub.apps.core.services.base import BaseService
from hub.apps.core.events.service_publishers import ContractEventPublisher

class ContractService(BaseService, ContractEventPublisher):
    """Service with event publishing capabilities."""

    def __init__(self, tenant_id=None, user_id=None):
        BaseService.__init__(self, tenant_id=tenant_id, user_id=user_id)
        ContractEventPublisher.__init__(self, tenant_id=tenant_id, user_id=user_id)

    def create_contract(self, contract_data):
        """Create contract and publish event."""
        contract = Contract.objects.create(**contract_data)

        # Publish event
        self.publish_contract_created(
            contract_id=str(contract.id),
            status=contract.status,
            tenant_id=self.tenant_id,
            user_id=self.user_id
        )

        return contract
```

#### Publisher Initialization Pattern

All publishers follow this initialization pattern:

```python
def __init__(self, *args, **kwargs):
    # Handle parent class initialization
    try:
        parent_init = super().__init__
        if parent_init is not object.__init__:
            parent_init(*args, **kwargs)
    except (TypeError, AttributeError):
        pass

    # Initialize internal EventPublisher
    self._event_publisher = EventPublisher(
        service_name="service_name",
        tenant_id=getattr(self, "tenant_id", None),
        user_id=getattr(self, "user_id", None),
    )
```

#### Publisher Method Pattern

All publisher methods follow this pattern:

```python
def publish_event_name(
    self,
    resource_id: str,
    optional_field: Optional[str] = None,
    **kwargs,
) -> str:
    """Publish event_name event."""
    return self._event_publisher.publish(
        event_type="domain.entity.action",
        data={
            "resource_id": resource_id,
            "optional_field": optional_field,
        },
        **kwargs,  # Pass through tenant_id, user_id, correlation_id, etc.
    )
```

#### Key Features

1. **Type Safety**: Each publisher method has typed parameters
2. **Deduplication**: Automatic duplicate event detection
3. **Error Handling**: Graceful error handling with logging
4. **Context Propagation**: Tenant and user context automatically included
5. **Extensibility**: Easy to add new event types via new methods

### Direct Event Publishing

For cases where a service-specific publisher doesn't exist, use the base `EventPublisher`:

```python
from hub.apps.core.events.publisher import EventPublisher

publisher = EventPublisher(
    service_name="my_service",
    tenant_id=tenant_id,
    user_id=user_id
)

event_id = publisher.publish(
    event_type="custom.event.type",
    data={"field": "value"},
    tags=["custom", "event"]
)
```

### Event Deduplication

All publishers support automatic event deduplication:

```python
# First publish
event_id_1 = service.publish_contract_created(contract_id="123")

# Duplicate publish (same event_type and data)
event_id_2 = service.publish_contract_created(contract_id="123")

# event_id_1 == event_id_2 (same event ID returned)
```

Deduplication uses Redis with configurable TTL (default: 24 hours).

### Event Publisher Pattern

The event publisher pattern provides a standardized way for services to publish events. This pattern ensures:

1. **Consistency**: All services publish events in the same way
2. **Type Safety**: Publisher methods have typed parameters
3. **Context Propagation**: Tenant and user context automatically included
4. **Error Handling**: Graceful error handling with logging
5. **Deduplication**: Automatic duplicate event detection
6. **Testability**: Easy to test event publishing

#### Pattern Components

1. **Mixin Class**: Each publisher is a mixin that can be added to service classes
2. **Internal EventPublisher**: Each publisher maintains an internal `EventPublisher` instance
3. **Typed Methods**: Each event type has a dedicated `publish_*` method
4. **Service Context**: Publishers automatically include service name, tenant_id, and user_id

#### Pattern Implementation Steps

1. **Create Publisher Mixin**:
```python
class MyServiceEventPublisher:
    """Event publisher mixin for MyService."""

    def __init__(self, *args, **kwargs):
        # Handle parent initialization
        try:
            parent_init = super().__init__
            if parent_init is not object.__init__:
                parent_init(*args, **kwargs)
        except (TypeError, AttributeError):
            pass

        # Initialize internal EventPublisher
        self._event_publisher = EventPublisher(
            service_name="my_service",
            tenant_id=getattr(self, "tenant_id", None),
            user_id=getattr(self, "user_id", None),
        )
```

2. **Add Publish Methods**:
```python
def publish_resource_created(
    self,
    resource_id: str,
    name: Optional[str] = None,
    **kwargs,
) -> str:
    """Publish resource.created event."""
    return self._event_publisher.publish(
        event_type="resource.created",
        data={
            "resource_id": resource_id,
            "name": name,
        },
        **kwargs,  # Pass through tenant_id, user_id, correlation_id, etc.
    )
```

3. **Use in Service**:
```python
class MyService(BaseService, MyServiceEventPublisher):
    def __init__(self, tenant_id=None, user_id=None):
        BaseService.__init__(self, tenant_id=tenant_id, user_id=user_id)
        MyServiceEventPublisher.__init__(self, tenant_id=tenant_id, user_id=user_id)

    def create_resource(self, resource_data):
        resource = Resource.objects.create(**resource_data)
        self.publish_resource_created(
            resource_id=str(resource.id),
            name=resource.name
        )
        return resource
```

#### Pattern Benefits

1. **Separation of Concerns**: Event publishing logic is separated from business logic
2. **Reusability**: Publishers can be reused across multiple services
3. **Testability**: Easy to test event publishing independently
4. **Maintainability**: Changes to event publishing don't affect business logic
5. **Type Safety**: Typed methods prevent errors at development time

#### Pattern Best Practices

1. **One Publisher Per Service**: Create one publisher mixin per service
2. **One Method Per Event Type**: Each event type should have its own publish method
3. **Consistent Naming**: Use `publish_<event_type>` naming convention
4. **Documentation**: Document all events published by your service
5. **Error Handling**: Handle errors gracefully, don't block business logic
6. **Testing**: Write tests for event publishing (use real EventBus, no mocks)

### Best Practices for Event Publishers

1. **Use Service-Specific Publishers**: Prefer service-specific publishers over direct `EventPublisher`
2. **Include Context**: Always include tenant_id and user_id when available
3. **Handle Errors Gracefully**: Event publishing failures should not block business logic
4. **Use Tags**: Include relevant tags for event filtering and monitoring
5. **Document Events**: Document all events published by your service
6. **Test Publishing**: Write tests for event publishing (use real EventBus, no mocks)

## Event Types

For a complete reference of all event types, see **[Event Types Reference](EVENT_TYPES_REFERENCE.md)**.

**Total Event Types**: 120+ unique event types across 23 publishers

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

