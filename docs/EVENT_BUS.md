# Event Bus

The Data Interoperability Hub uses Redis pub/sub as its event bus for cross-service communication.

## Publishers by service

### api-service
The api-service publishes events for:
- Asset lifecycle changes (created, updated, deleted, activated)
- Contract lifecycle (published, archived)
- Compliance run results
- DQ run results
- Marketplace order fulfillment
- Governance access request transitions
- User and tenant mutations

### Microservices (N/A)
The following microservices do not publish events directly; they consume events from the bus:
- semantic-service (N/A)
- dq-service (N/A)
- compliance-service (N/A)
- webhook-service (N/A)

## Event format
All events carry `event_type`, `tenant_id`, `resource_id`, `timestamp`, and an opaque `payload` JSON blob.

## Retention
Events are ephemeral (fire-and-forget pub/sub); the audit log is the durable record.

## Event Publisher Pattern

Event publishers follow a consistent pattern across services. Each publisher class is registered in the
service layer and injected via the event bus configuration.

### Usage Example

```python
class MyService:
    """Example service that publishes events via the event bus."""

    def __init__(self, event_bus):
        self.event_bus = event_bus

    def process(self, data):
        # Business logic here
        self.event_bus.publish("my.event_type", payload=data)
```

### Publisher Services

The following service-layer classes act as event publishers:

- **ContractService** — Publishes contract lifecycle events (created, published, archived) and
  contract status transitions.
- **AssetService** — Publishes asset lifecycle events and activation state changes.
- **DatasetService** — Publishes dataset creation and metadata update events.
- **MarketplaceService** — Publishes listing, order, and entitlement events.
- **GovernanceService** — Publishes access request, approval, and policy change events.
