# Service Integration Patterns

## Overview

This document describes the standard integration patterns used in the Data Interoperability Hub for service-to-service communication. These patterns ensure reliable, scalable, and maintainable inter-service coordination.

## Table of Contents

1. [Pattern 1: Direct Service Calls (Synchronous)](#pattern-1-direct-service-calls-synchronous)
2. [Pattern 2: Event-Driven Coordination (Asynchronous)](#pattern-2-event-driven-coordination-asynchronous)
3. [Pattern 3: Workflow Orchestration (Multi-Step)](#pattern-3-workflow-orchestration-multi-step)
4. [Pattern Selection Criteria](#pattern-selection-criteria)
5. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)

---

## Pattern 1: Direct Service Calls (Synchronous)

### When to Use

- **Simple operations** that require immediate response
- **Real-time validation** or data retrieval needed
- **Low latency requirements** (< 1 second response time)
- **Strong consistency** required (cannot tolerate eventual consistency)
- **Simple request-response** interactions without complex state management

### Pattern Architecture

```
Service A → HTTP/REST → Service B
         ← Response ←
```

### Implementation

#### Service Client Pattern

All service clients follow a consistent pattern with:
- HTTP client (httpx) with connection pooling
- Retry logic with exponential backoff
- Circuit breaker for fault tolerance
- Distributed tracing support
- Health check capabilities

#### Example: ComplianceServiceClient

**Location**: `hub/apps/compliance/service_client.py`

```python
from hub.apps.core.error_handling.error_recovery import CircuitBreaker
from hub.apps.core.redis import get_redis_client
import httpx
import time

class ComplianceServiceClient:
    """Client for interacting with the Compliance service."""

    def __init__(self):
        self.base_url = getattr(settings, 'COMPLIANCE_SERVICE_URL', 'http://compliance-service:8082')
        self.timeout = getattr(settings, 'COMPLIANCE_SERVICE_TIMEOUT', 1800)
        self.client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
        self.max_retries = 2
        self.backoff_factor = 1

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            service_name="compliance-service",
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
            redis_client=get_redis_client()
        )

    def _request_with_retry(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Helper to make HTTP requests with retry logic"""
        # Add trace headers for distributed tracing
        from hub.apps.api.middleware.trace_propagation import get_trace_headers
        trace_headers = get_trace_headers()
        if trace_headers:
            kwargs.setdefault('headers', {}).update(trace_headers)

        # Retry logic with exponential backoff
        for attempt in range(self.max_retries + 1):
            try:
                # Use circuit breaker to protect against cascading failures
                response = self._circuit_breaker.call(
                    lambda: self.client.request(method, endpoint, **kwargs)
                )
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                # Retry on 5xx errors
                if e.response.status_code >= 500 and attempt < self.max_retries:
                    delay = self.backoff_factor * (2 ** attempt)
                    logger.warning(f"Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                raise
            except httpx.RequestError as e:
                # Retry on network errors
                if attempt < self.max_retries:
                    delay = self.backoff_factor * (2 ** attempt)
                    logger.warning(f"Network error, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                raise

    def scan_asset(self, asset_id: str, tenant_id: str) -> dict:
        """Scan asset for compliance violations"""
        response = self._request_with_retry(
            "POST",
            "/scan",
            json={"asset_id": asset_id, "tenant_id": tenant_id}
        )
        return response.json()
```

#### Other Service Clients

- **DQServiceClient** (`hub/apps/dq/service_client.py`) - Data quality checks
- **SemanticServiceClient** (`hub/apps/semantic/service_client.py`) - RDF mapping operations
- **DataContractCLIClient** (`hub/apps/contracts/cli_client.py`) - Contract validation

### Error Handling

#### Retry Logic

**Strategy**: Exponential backoff with configurable max retries

- **Base delay**: 1 second
- **Backoff factor**: 2 (doubles each retry)
- **Max retries**: 2-3 attempts (configurable per service)
- **Retryable errors**: 5xx HTTP status codes, network errors
- **Non-retryable errors**: 4xx HTTP status codes (client errors)

**Example**:
```python
# Retry delays: 1s, 3s, 7s (if max_retries=3)
delay = backoff_factor * (2 ** attempt)
```

#### Circuit Breaker

**Purpose**: Prevent cascading failures when downstream service is unavailable

**States**:
- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Too many failures detected, requests rejected immediately
- **HALF_OPEN**: Testing recovery, allows limited requests

**Configuration**:
- **Failure threshold**: 5 consecutive failures
- **Success threshold**: 2 successful requests to close circuit
- **Timeout**: 60 seconds before transitioning to HALF_OPEN

**Implementation**: `hub/apps/core/error_handling/error_recovery.py`

```python
from hub.apps.core.error_handling.error_recovery import CircuitBreaker

circuit_breaker = CircuitBreaker(
    service_name="compliance-service",
    failure_threshold=5,
    timeout_seconds=60,
    success_threshold=2,
    redis_client=get_redis_client()
)

# Usage
response = circuit_breaker.call(lambda: service_client.request(...))
```

### Transaction Management

#### Distributed Transactions

For operations requiring ACID guarantees across services:

1. **Two-Phase Commit (2PC)**: Not recommended due to blocking nature
2. **Saga Pattern**: Preferred for distributed transactions (see Pattern 3)
3. **Compensating Actions**: Use workflow orchestration for complex multi-service transactions

**Example**: Contract creation with validation
```python
# Service A: Create contract
contract = contract_service.create_contract(...)

# Service B: Validate contract (if fails, compensate)
try:
    validation_result = validation_service.validate(contract.id)
except ValidationError:
    # Compensate: Delete contract
    contract_service.delete_contract(contract.id)
    raise
```

### Use Cases

- **API Service → Compliance Service**: Real-time compliance scanning
- **API Service → DQ Service**: Data quality validation
- **API Service → Semantic Service**: RDF mapping operations
- **API Service → DataContract Service**: Contract validation

### Performance Characteristics

- **Latency**: < 100ms (P50), < 500ms (P95)
- **Throughput**: ~100-1000 requests/second per service
- **Availability**: 99.9% (with circuit breaker protection)

---

## Pattern 2: Event-Driven Coordination (Asynchronous)

### When to Use

- **Decoupled operations** where services don't need immediate response
- **Eventual consistency** is acceptable
- **Scalability** requirements (high throughput)
- **Multiple subscribers** need to react to same event
- **Long-running operations** that shouldn't block request flow
- **Cross-cutting concerns** (logging, auditing, notifications)

### Pattern Architecture

```
Service A → Event Bus (Redis Pub/Sub) → Service B (Subscriber)
         ↓                              ↓
    PostgreSQL                      Service C (Subscriber)
    (Persistence)                  Service D (Subscriber)
```

### Implementation

#### Event Bus Architecture

**Components**:
- **Redis Pub/Sub**: Real-time event delivery (fire-and-forget)
- **PostgreSQL**: Event persistence for replay, audit, and debugging
- **Dead Letter Queue**: Failed event storage
- **Event Schema**: JSON Schema validation

**Location**: `hub/apps/core/events/`

#### Event Publishing

**Using EventPublisher Class**:

```python
from hub.apps.core.events import EventPublisher

# Initialize publisher
publisher = EventPublisher(
    service_name="contract_service",
    tenant_id=tenant_id,
    user_id=user_id
)

# Publish event
event_id = publisher.publish(
    event_type="contract.created",
    data={
        "contract_id": str(contract.id),
        "asset_id": str(asset.id),
        "spec_type": contract.original_spec_type
    },
    correlation_id=correlation_id,
    tags=["contract", "odcs"]
)
```

**Using Decorator**:

```python
from hub.apps.core.events import event_publisher

@event_publisher('contract.created', tenant_id=tenant_id)
def create_contract(contract_data: dict) -> dict:
    contract = Contract.objects.create(**contract_data)
    return {"contract_id": str(contract.id)}
```

**Using Function**:

```python
from hub.apps.core.events import publish_event

event_id = publish_event(
    event_type="contract.created",
    data={"contract_id": str(contract.id)},
    tenant_id=tenant_id,
    user_id=user_id
)
```

#### Event Subscription

**Using EventSubscriber Class**:

```python
from hub.apps.core.events import EventSubscriber

def handle_contract_created(event: dict):
    """Handle contract.created events"""
    contract_id = event["data"]["contract_id"]
    # Update search index
    search_service.index_contract(contract_id)
    # Send notification
    notification_service.notify_contract_created(contract_id)

# Subscribe to events
subscriber = EventSubscriber("search_service")
subscriber.subscribe("contract.created", handle_contract_created)
subscriber.subscribe("contract.updated", handle_contract_updated)
subscriber.subscribe("contract.*", handle_all_contract_events)  # Pattern matching
```

**Using Decorator**:

```python
from hub.apps.core.events import event_subscriber

@event_subscriber('search_service', 'contract.*')
def handle_contract_events(event: dict):
    """Handle all contract events"""
    event_type = event["event_type"]
    contract_id = event["data"]["contract_id"]

    if event_type == "contract.created":
        search_service.index_contract(contract_id)
    elif event_type == "contract.updated":
        search_service.update_contract_index(contract_id)
    elif event_type == "contract.deleted":
        search_service.remove_contract_index(contract_id)
```

#### Event Schema

**Base Event Structure**:

```json
{
  "event_id": "uuid",
  "event_type": "contract.created",
  "event_version": "1.0.0",
  "timestamp": "2025-01-15T10:00:00Z",
  "source": {
    "service": "contract_service",
    "tenant_id": "uuid",
    "user_id": "uuid",
    "request_id": "request-id"
  },
  "data": {
    "contract_id": "uuid",
    "asset_id": "uuid"
  },
  "metadata": {
    "correlation_id": "correlation-id",
    "causation_id": "uuid",
    "tags": ["contract", "odcs"]
  }
}
```

**Event Type Format**: `domain.entity.action` (e.g., `contract.created`, `asset.activated`)

### Error Handling

#### Dead Letter Queue

Failed events are automatically moved to Dead Letter Queue (DLQ) for manual inspection and replay.

**Location**: `hub/apps/core/events/models.py` - `DeadLetterQueue` model

**Replay Failed Events**:

```python
from hub.apps.core.events import get_event_bus

event_bus = get_event_bus()

# Replay events from DLQ
failed_events = DeadLetterQueue.objects.filter(
    event_type="contract.created",
    created_at__gte=timezone.now() - timedelta(hours=1)
)

for failed_event in failed_events:
    event_bus.replay_event(failed_event.event_id)
```

#### Retry Logic

Event handlers should implement their own retry logic:

```python
from hub.apps.core.error_handling.error_recovery import with_retry

@with_retry(
    max_attempts=3,
    base_delay=1.0,
    max_delay=60.0,
    retry_strategy=RetryStrategy.EXPONENTIAL_BACKOFF
)
def handle_contract_created(event: dict):
    """Handle contract.created events with retry"""
    contract_id = event["data"]["contract_id"]
    search_service.index_contract(contract_id)
```

### Transaction Management

#### Saga Pattern

For multi-step operations requiring eventual consistency:

1. **Choreography**: Services coordinate through events (preferred for simple flows)
2. **Orchestration**: Central coordinator manages workflow (see Pattern 3)

**Example: Contract Creation Saga**:

```python
# Step 1: Create contract
contract = contract_service.create_contract(...)
publish_event("contract.created", {"contract_id": contract.id})

# Step 2: Validate contract (async)
@event_subscriber('validation_service', 'contract.created')
def validate_contract(event):
    contract_id = event["data"]["contract_id"]
    try:
        validation_result = validation_service.validate(contract_id)
        publish_event("contract.validated", {"contract_id": contract_id})
    except ValidationError as e:
        publish_event("contract.validation_failed", {
            "contract_id": contract_id,
            "error": str(e)
        })

# Step 3: Compensate on failure
@event_subscriber('contract_service', 'contract.validation_failed')
def compensate_contract_creation(event):
    contract_id = event["data"]["contract_id"]
    contract_service.delete_contract(contract_id)
    publish_event("contract.deleted", {"contract_id": contract_id})
```

### Use Cases

- **Contract Created → Semantic Mapping**: Asynchronous RDF mapping
- **Asset Updated → Search Index Update**: Decoupled indexing
- **Compliance Scan Completed → Notifications**: Event-driven notifications
- **Contract Validated → Workflow Progression**: State machine transitions

### Performance Characteristics

- **Latency**: < 100ms (P50) for event delivery
- **Throughput**: ~1,500-2,000 events/second
- **Persistence**: 100% of events persisted to PostgreSQL
- **Availability**: 99.9% (Redis Pub/Sub + PostgreSQL persistence)

---

## Pattern 3: Workflow Orchestration (Multi-Step)

### When to Use

- **Complex multi-step operations** requiring coordination
- **State management** needed across multiple steps
- **Compensation logic** required for rollback
- **Long-running processes** (minutes to hours)
- **Conditional branching** based on step results
- **Parallel execution** of independent steps
- **Progress tracking** and resumability needed

### Pattern Architecture

```
Workflow Engine → Step 1 (Service A)
              → Step 2 (Service B)
              → Step 3 (Service C)
              ↓
         State Management
         (PostgreSQL)
```

### Implementation

#### Workflow Engine

**Location**: `hub/apps/orchestration/workflow_engine.py`

**Key Features**:
- Workflow DSL (JSON/YAML) for defining workflows
- Step execution with retry logic
- Compensation (Saga pattern) for rollback
- State management and progress tracking
- Event publishing for workflow lifecycle

#### Workflow DSL

**Location**: `hub/apps/orchestration/WORKFLOW_DSL.md`

**Simple Sequential Workflow**:

```json
{
  "version": "1.0.0",
  "steps": [
    {
      "name": "validate_contract",
      "type": "task",
      "task": "validate_contract_task",
      "input": {
        "contract_id": "{{input.contract_id}}"
      }
    },
    {
      "name": "normalize_contract",
      "type": "task",
      "task": "normalize_contract_task",
      "input": {
        "contract_id": "{{state.contract_id}}"
      }
    },
    {
      "name": "publish_contract",
      "type": "task",
      "task": "publish_contract_task",
      "input": {
        "contract_id": "{{state.contract_id}}"
      }
    }
  ]
}
```

**Workflow with Compensation**:

```json
{
  "version": "1.0.0",
  "compensation": {
    "enabled": true
  },
  "steps": [
    {
      "name": "create_contract",
      "type": "task",
      "task": "create_contract_task",
      "compensation": {
        "type": "task",
        "task": "delete_contract_task"
      }
    },
    {
      "name": "validate_contract",
      "type": "task",
      "task": "validate_contract_task",
      "compensation": {
        "type": "task",
        "task": "revert_validation_task"
      }
    }
  ]
}
```

**Workflow with Conditional Branching**:

```json
{
  "version": "1.0.0",
  "steps": [
    {
      "name": "check_contract_status",
      "type": "task",
      "task": "check_status_task"
    },
    {
      "name": "conditional_process",
      "type": "conditional",
      "condition": {
        "operator": "equals",
        "field": "status",
        "value": "active"
      },
      "then": [
        {
          "name": "activate_contract",
          "type": "task",
          "task": "activate_contract_task"
        }
      ],
      "else": [
        {
          "name": "deactivate_contract",
          "type": "task",
          "task": "deactivate_contract_task"
        }
      ]
    }
  ]
}
```

#### Creating and Executing Workflows

**Create Workflow Instance**:

```python
from hub.apps.orchestration.workflow_engine import WorkflowEngine

workflow_engine = WorkflowEngine()

# Create workflow instance
instance = workflow_engine.create_instance(
    workflow_name="contract_creation",
    input_data={
        "contract_id": contract_id,
        "tenant_id": tenant_id
    },
    tenant_id=tenant_id,
    created_by_id=user_id
)

# Start workflow execution
workflow_engine.start_instance(instance.id)

# Execute workflow (runs synchronously or asynchronously)
workflow_engine.execute_instance(instance.id)
```

**Register Task Functions**:

```python
def validate_contract_task(workflow_instance, step, input_data, state_data):
    """Task function for contract validation"""
    contract_id = input_data.get("contract_id")

    # Perform validation
    validation_result = contract_service.validate_contract(contract_id)

    # Return step output (merged into state_data)
    return {
        "validation_result": validation_result,
        "contract_id": contract_id,
        "status": "validated"
    }

# Register task
workflow_engine.register_task("validate_contract_task", validate_contract_task)
```

#### Saga Pattern Implementation

**Location**: `hub/apps/orchestration/saga.py`

**Saga Orchestrator**:

```python
from hub.apps.orchestration.saga import SagaOrchestrator, SagaStep

# Define saga steps
steps = [
    SagaStep(
        name="create_contract",
        execute=lambda state: contract_service.create_contract(...),
        compensate=lambda state: contract_service.delete_contract(state["contract_id"])
    ),
    SagaStep(
        name="validate_contract",
        execute=lambda state: validation_service.validate(state["contract_id"]),
        compensate=lambda state: None  # No compensation needed
    ),
    SagaStep(
        name="publish_contract",
        execute=lambda state: publish_service.publish(state["contract_id"]),
        compensate=lambda state: publish_service.unpublish(state["contract_id"])
    )
]

# Execute saga
saga = SagaOrchestrator()
result = saga.execute(steps, initial_state={"tenant_id": tenant_id})

# If any step fails, all previous steps are compensated in reverse order
```

### Error Handling

#### Retry Logic

Workflow steps automatically retry on failure:

```json
{
  "name": "validate_contract",
  "type": "retry",
  "max_retries": 3,
  "steps": [
    {
      "name": "validate_step",
      "type": "task",
      "task": "validate_contract_task"
    }
  ]
}
```

#### Compensation

Compensation is automatically executed on workflow failure:

1. **Forward execution**: Steps execute sequentially
2. **Failure detected**: Step fails, compensation triggered
3. **Reverse compensation**: Previous steps compensated in reverse order
4. **State restoration**: System restored to initial state

**Example**:

```python
# Step 1: Create contract (succeeds)
contract = contract_service.create_contract(...)

# Step 2: Validate contract (fails)
try:
    validation_service.validate(contract.id)
except ValidationError:
    # Compensation: Delete contract (Step 1 compensation)
    contract_service.delete_contract(contract.id)
    raise WorkflowExecutionError("Validation failed")
```

### Transaction Management

#### Saga Pattern with Compensation

The workflow engine implements the Saga pattern for distributed transactions:

- **No distributed locks**: Each step commits independently
- **Compensating actions**: Each step defines compensation logic
- **Eventual consistency**: System eventually consistent after compensation

**Compensation Flow**:

```
Step 1 (Create) → Step 2 (Validate) → Step 3 (Publish)
     ↓ (fails)
Compensate Step 2 → Compensate Step 1
```

### Use Cases

- **Asset Creation Workflow**: Multi-step asset onboarding with validation
- **Contract Creation Workflow**: Contract creation, validation, normalization, publishing
- **Transformation Pipeline Workflow**: Pipeline execution with quality checks
- **Marketplace Publishing Workflow**: Publishing with transformation and quality validation

### Performance Characteristics

- **Latency**: Variable (seconds to hours depending on workflow complexity)
- **Throughput**: ~10-100 workflows/second
- **State Management**: PostgreSQL-backed, durable
- **Resumability**: Workflows can be paused and resumed

---

## Pattern Selection Criteria

### Decision Matrix

| Criteria | Direct Calls | Event-Driven | Workflow Orchestration |
|----------|-------------|--------------|----------------------|
| **Response Time** | < 1 second | < 100ms (event delivery) | Variable (seconds to hours) |
| **Consistency** | Strong | Eventual | Eventual (with compensation) |
| **Coupling** | Tight | Loose | Medium |
| **Scalability** | Medium | High | Medium |
| **Complexity** | Low | Medium | High |
| **State Management** | None | Event log | Full state tracking |
| **Error Handling** | Retry + Circuit Breaker | DLQ + Retry | Compensation + Retry |
| **Use Case** | Simple operations | Decoupled operations | Complex multi-step |

### Selection Guidelines

#### Choose Direct Service Calls When:

- ✅ Immediate response required (< 1 second)
- ✅ Strong consistency needed
- ✅ Simple request-response interaction
- ✅ Low latency critical
- ✅ Synchronous validation or data retrieval

**Example**: Contract validation during creation, real-time compliance scanning

#### Choose Event-Driven When:

- ✅ Decoupled operations acceptable
- ✅ Eventual consistency acceptable
- ✅ Multiple subscribers needed
- ✅ High throughput required
- ✅ Long-running operations shouldn't block

**Example**: Search index updates, notifications, audit logging

#### Choose Workflow Orchestration When:

- ✅ Complex multi-step operations
- ✅ State management required
- ✅ Compensation logic needed
- ✅ Conditional branching required
- ✅ Progress tracking needed

**Example**: Asset onboarding workflow, contract creation with validation and normalization

### Hybrid Approaches

**Combining Patterns**:

1. **Direct Call + Event Publishing**: Call service directly, then publish event for downstream processing
   ```python
   # Direct call for immediate response
   result = compliance_service.scan_asset(asset_id)

   # Event for downstream processing
   publish_event("compliance.scan.completed", {"asset_id": asset_id, "result": result})
   ```

2. **Workflow + Event-Driven**: Workflow orchestrates steps, events trigger workflow progression
   ```python
   # Workflow step publishes event
   publish_event("contract.validated", {"contract_id": contract_id})

   # Event triggers next workflow step
   @event_subscriber('workflow_engine', 'contract.validated')
   def proceed_to_normalization(event):
       workflow_engine.execute_next_step(workflow_instance_id)
   ```

---

## Real-World Examples

This section provides comprehensive, real-world examples from the codebase demonstrating each integration pattern with actual code and tests.

### Example 1: Direct Service Call (ContractService → AssetService)

**Use Case**: AssetService needs to link an ODPS contract to an asset, requiring validation from ContractService.

**Location**: `hub/apps/assets/services.py` (lines 412-500)

**Implementation**:

```python
from hub.apps.assets.services import AssetService
from hub.apps.contracts.services import ContractService, ODPSService
from hub.apps.contracts.models import Contract, OriginalSpecType
from hub.apps.core.exceptions import NotFoundError, ValidationError

class AssetService(BaseService):
    """Service for asset operations."""

    def link_odps_contract_to_asset(
        self,
        asset_id: str,
        odps_contract_id: Optional[str] = None,
        odps_raw: Optional[str] = None,
        odps_format: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Contract:
        """
        Link ODPS contract to asset using direct service calls.

        This method demonstrates Pattern 1: Direct Service Calls
        - Synchronous validation via ContractService
        - Immediate response required
        - Strong consistency needed
        """
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        def _link():
            # Step 1: Get asset (direct database access)
            asset = self.get_resource_or_raise(
                Asset,
                asset_id,
                tenant_id=effective_tenant_id
            )

            # Step 2: Direct service call to ODPSService
            odps_service = ODPSService(
                tenant_id=effective_tenant_id,
                user_id=effective_user_id
            )

            if odps_contract_id:
                # Step 3: Direct service call to ContractService for validation
                contract_service = ContractService(
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id
                )

                # Synchronous call - waits for response
                odps_contract = contract_service.get_contract(
                    contract_id=odps_contract_id,
                    tenant_id=effective_tenant_id
                )

                # Step 4: Validate contract type (synchronous validation)
                if odps_contract.original_spec_type != OriginalSpecType.ODPS:
                    raise ValidationError(
                        f"Contract {odps_contract_id} is not an ODPS contract",
                        code="INVALID_CONTRACT_TYPE"
                    )

                # Step 5: Link contract to asset (atomic operation)
                odps_contract.asset = asset
                odps_contract.version = self._calculate_version(asset, effective_tenant_id)
                odps_contract.save(update_fields=['asset', 'version'])

                return odps_contract
            elif odps_raw:
                # Direct service call to create new ODPS contract
                odps_contract = odps_service.create_odps(
                    odps_raw=odps_raw,
                    odps_format=odps_format or "json",
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                    asset_id=asset_id
                )
                return odps_contract

        # Execute within transaction for atomicity
        return self.execute_with_metrics(
            operation="link_odps_contract_to_asset",
            tenant_id=effective_tenant_id,
            func=_link
        )
```

**Test Example**:

**Location**: `hub/apps/contracts/tests/test_odps_service_integration.py` (lines 300-330)

```python
from django.test import TestCase
from hub.apps.assets.services import AssetService
from hub.apps.contracts.services import ODPSService
from hub.apps.contracts.models import OriginalSpecType
from hub.apps.assets.models import Asset, AssetStatus

class AssetServiceODPSIntegrationTest(TestCase):
    """Tests for AssetService integration with ODPSService."""

    def test_link_odps_contract_to_asset_with_existing_contract(self):
        """Test direct service call pattern: AssetService → ContractService."""
        # Setup: Create ODPS contract
        odps_service = ODPSService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        odps_contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Execute: Direct service call
        asset_service = AssetService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        linked_contract = asset_service.link_odps_contract_to_asset(
            asset_id=str(self.asset.id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify: Synchronous response with strong consistency
        self.assertIsNotNone(linked_contract)
        self.assertEqual(linked_contract.asset, self.asset)
        self.assertEqual(linked_contract.original_spec_type, OriginalSpecType.ODPS)

        # Verify: Contract version calculated synchronously
        self.assertGreater(linked_contract.version, 0)
```

**Key Characteristics**:
- ✅ Synchronous execution (waits for response)
- ✅ Strong consistency (immediate validation)
- ✅ Error handling via exceptions
- ✅ Transaction management for atomicity
- ✅ Direct service-to-service communication

---

### Example 2: Event-Driven Coordination (ContractService → Event Bus → SearchService)

**Use Case**: When an ODPS contract is created, multiple services need to be notified (SearchService for indexing, NotificationService for alerts, AuditService for logging).

**Location**: `hub/apps/contracts/services.py` (lines 2400-2440)

**Implementation**:

```python
from hub.apps.core.events.service_publishers import ODPSEventPublisher
from hub.apps.contracts.models import Contract

class ODPSService(BaseService, ODPSEventPublisher):
    """Service for ODPS contract operations."""

    @transaction.atomic
    def create_odps(
        self,
        odps_raw: str,
        odps_format: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        asset_id: Optional[str] = None
    ) -> Contract:
        """
        Create ODPS contract and publish events.

        This method demonstrates Pattern 2: Event-Driven Coordination
        - Decoupled operations (search indexing, notifications)
        - Eventual consistency acceptable
        - Multiple subscribers can react
        """
        # ... contract creation logic ...

        # Publish event to event bus (asynchronous, fire-and-forget)
        try:
            event_id = self.publish_odps_created(
                contract_id=str(contract.id),
                asset_id=str(asset.id) if asset else None,
                status=contract.status,
                odps_version=odps_version,
                original_format=contract.original_format
            )

            # Track event ID for compensation if needed
            if event_id and state.events_published is not None:
                state.events_published.append(str(event_id))

        except Exception as e:
            # If event publishing fails, compensate
            logger.exception(
                "odps_created_event_publish_failed",
                contract_id=str(contract.id),
                error=str(e),
                message="Failed to publish ODPS created event, triggering compensation"
            )

            # Compensation logic (Saga pattern)
            compensation.compensate(
                state=state,
                rollback_contract=True,
                cleanup_resources=True,
                restore_state=True,
                publish_compensation_events=True
            )
            raise ValidationError(
                message=f"Failed to publish ODPS created event: {str(e)}",
                code="ODPS_EVENT_PUBLISH_FAILED"
            ) from e

        return contract
```

**Event Publisher Implementation**:

**Location**: `hub/apps/core/events/service_publishers.py`

```python
class ODPSEventPublisher:
    """Event publisher for ODPS-related events."""

    def publish_odps_created(
        self,
        contract_id: str,
        asset_id: Optional[str] = None,
        status: str = None,
        odps_version: str = None,
        original_format: str = None
    ) -> str:
        """
        Publish odps.created event to event bus.

        Subscribers:
        - SearchService: Index contract for search
        - NotificationService: Send creation notifications
        - AuditService: Log contract creation
        """
        from hub.apps.core.events.publisher import EventPublisher

        publisher = EventPublisher(
            service_name="contract_service",
            tenant_id=self.tenant_id,
            user_id=self.user_id
        )

        event_id = publisher.publish(
            event_type="odps.created",
            data={
                "contract_id": contract_id,
                "asset_id": asset_id,
                "status": status,
                "odps_version": odps_version,
                "original_format": original_format
            },
            tags=["odps", "contract", "product"]
        )

        return event_id
```

**Event Subscriber Implementation**:

**Location**: `hub/apps/search/indexing.py` (example)

```python
from hub.apps.core.events.subscriber import EventSubscriber
from hub.apps.core.events.bus import get_event_bus

class SearchIndexer:
    """Service for indexing contracts in search."""

    def __init__(self):
        self.event_bus = get_event_bus()
        self._subscribe_to_events()

    def _subscribe_to_events(self):
        """Subscribe to ODPS events for indexing."""
        subscriber = EventSubscriber("search_service")

        # Subscribe to ODPS created events
        subscriber.subscribe(
            "odps.created",
            self._handle_odps_created
        )

        # Subscribe to ODPS updated events
        subscriber.subscribe(
            "odps.updated",
            self._handle_odps_updated
        )

    def _handle_odps_created(self, event: dict):
        """Handle odps.created event - index contract for search."""
        try:
            contract_id = event["data"]["contract_id"]
            asset_id = event["data"].get("asset_id")

            # Index contract asynchronously
            self.index_contract(contract_id, asset_id)

            logger.info(
                "Contract indexed from event",
                contract_id=contract_id,
                event_id=event["event_id"]
            )
        except Exception as e:
            # Event automatically moved to Dead Letter Queue
            logger.error(
                "Failed to index contract from event",
                contract_id=event["data"].get("contract_id"),
                error=str(e),
                event_id=event.get("event_id")
            )
            raise  # Re-raise to trigger DLQ

    def index_contract(self, contract_id: str, asset_id: Optional[str] = None):
        """Index contract in search engine."""
        # ... indexing logic ...
        pass
```

**Test Example**:

**Location**: `hub/apps/contracts/tests/test_odps_event_bus_integration.py`

```python
from django.test import TestCase, override_settings
from hub.apps.contracts.services import ODPSService
from hub.apps.core.events.models import Event

@override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False)
class ODPSEventPublishingTest(TestCase):
    """Tests for ODPS event publishing."""

    def test_odps_created_event_published(self):
        """Test event-driven pattern: ContractService → Event Bus → Subscribers."""
        # Setup: Create ODPS service
        odps_service = ODPSService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Execute: Create ODPS contract (publishes event)
        contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify: Event was published to PostgreSQL
        events = Event.objects.filter(
            event_type="odps.created",
            tenant_id=self.tenant.id
        )

        self.assertGreater(events.count(), 0, "Event should be persisted")

        # Verify: Event contains correct data
        contract_event = events.first()
        self.assertEqual(contract_event.event_type, "odps.created")
        event_data = contract_event.data if isinstance(contract_event.data, dict) else {}
        self.assertEqual(event_data.get("contract_id"), str(contract.id))

        # Note: In production, subscribers would process events asynchronously
        # SearchService would index the contract
        # NotificationService would send notifications
```

**Key Characteristics**:
- ✅ Asynchronous execution (fire-and-forget)
- ✅ Eventual consistency (subscribers process independently)
- ✅ Multiple subscribers (search, notifications, audit)
- ✅ Dead Letter Queue for failed events
- ✅ Saga pattern for compensation

---

### Example 3: Workflow Orchestration (ProductCreationWorkflow)

**Use Case**: Creating an ODPS product requires multiple coordinated steps: parsing, validation, normalization, contract creation, linking, indexing, and semantic mapping.

**Location**: `hub/apps/orchestration/workflows/product_creation.py`

**Workflow Definition**:

```python
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.models import WorkflowInstance

class ProductCreationWorkflow:
    """
    Product creation workflow orchestrator (ODPS Product-First flow).

    This workflow demonstrates Pattern 3: Workflow Orchestration
    - Complex multi-step operations
    - State management across steps
    - Compensation logic for rollback
    - Retry logic for transient failures
    """

    WORKFLOW_NAME = "product_creation"

    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """Register workflow definition with DSL."""
        workflow_dsl = {
            "version": "1.0.0",
            "dependencies": [],
            "steps": [
                {
                    "name": "parse_odps",
                    "type": "task",
                    "task": "product_creation.parse_odps"
                },
                {
                    "name": "resolve_refs",
                    "type": "task",
                    "task": "product_creation.resolve_refs",
                    "dependencies": ["parse_odps"]
                },
                {
                    "name": "extract_contract",
                    "type": "task",
                    "task": "product_creation.extract_contract",
                    "dependencies": ["resolve_refs"]
                },
                {
                    "name": "validate_odcs",
                    "type": "task",
                    "task": "product_creation.validate_odcs",
                    "dependencies": ["extract_contract"]
                },
                {
                    "name": "normalize_odcs",
                    "type": "task",
                    "task": "product_creation.normalize_odcs",
                    "dependencies": ["validate_odcs"],
                    "compensation": {
                        "type": "task",
                        "task": "product_creation.rollback_normalize_odcs"
                    }
                },
                {
                    "name": "create_odcs_contract",
                    "type": "task",
                    "task": "product_creation.create_odcs_contract",
                    "dependencies": ["normalize_odcs"],
                    "compensation": {
                        "type": "task",
                        "task": "product_creation.rollback_odcs_contract"
                    }
                },
                {
                    "name": "create_odps_contract",
                    "type": "task",
                    "task": "product_creation.create_odps_contract",
                    "dependencies": ["create_odcs_contract"],
                    "compensation": {
                        "type": "task",
                        "task": "product_creation.rollback_odps_contract"
                    }
                },
                {
                    "name": "link_contracts",
                    "type": "task",
                    "task": "product_creation.link_contracts",
                    "dependencies": ["create_odps_contract"],
                    "compensation": {
                        "type": "task",
                        "task": "product_creation.rollback_link_contracts"
                    }
                },
                {
                    "name": "index_for_search",
                    "type": "task",
                    "task": "product_creation.index_for_search",
                    "dependencies": ["link_contracts"]
                },
                {
                    "name": "semantic_mapping",
                    "type": "task",
                    "task": "product_creation.semantic_mapping",
                    "dependencies": ["index_for_search"]
                }
            ],
            "compensation": {
                "enabled": True
            }
        }

        registry.register_workflow(
            workflow_name=cls.WORKFLOW_NAME,
            dsl_json=workflow_dsl,
            description="Orchestrates ODPS product creation with validation, normalization, linking, indexing, and semantic mapping"
        )
```

**Workflow Task Implementation**:

```python
    @staticmethod
    def _create_odcs_contract_task(
        input_data: Dict[str, Any],
        instance: WorkflowInstance,
        step
    ) -> Dict[str, Any]:
        """
        Create ODCS contract from normalized data.

        This task demonstrates:
        - State management (contract_id stored in state_data)
        - Error handling (raises exceptions for workflow engine)
        - Compensation support (rollback task registered)
        """
        from hub.apps.contracts.services import ContractService

        tenant_id = input_data.get("tenant_id")
        user_id = input_data.get("user_id")
        normalized_odcs = input_data.get("normalized_odcs")

        # Create contract service
        contract_service = ContractService(
            tenant_id=tenant_id,
            user_id=user_id
        )

        # Create ODCS contract
        odcs_contract = contract_service.create_contract(
            original_raw=normalized_odcs["original_raw"],
            original_format=normalized_odcs["original_format"],
            tenant_id=tenant_id,
            user_id=user_id,
            original_spec_type="ODCS"
        )

        # Update workflow state
        state_data = instance.state_data or {}
        state_data["odcs_contract_id"] = str(odcs_contract.id)
        instance.state_data = state_data
        instance.save(update_fields=["state_data", "updated_at"])

        logger.info(
            "ODCS contract created in workflow",
            workflow_instance_id=str(instance.id),
            contract_id=str(odcs_contract.id)
        )

        return {
            "odcs_contract_id": str(odcs_contract.id),
            "state": state_data
        }

    @staticmethod
    def _rollback_odcs_contract_task(
        input_data: Dict[str, Any],
        instance: WorkflowInstance,
        step
    ) -> Dict[str, Any]:
        """
        Compensation task: Delete ODCS contract if workflow fails.

        This demonstrates Saga pattern compensation logic.
        """
        from hub.apps.contracts.models import Contract

        state_data = instance.state_data or {}
        odcs_contract_id = state_data.get("odcs_contract_id")

        if odcs_contract_id:
            try:
                odcs_contract = Contract.objects.get(id=odcs_contract_id)
                odcs_contract.delete()

                logger.info(
                    "ODCS contract rolled back",
                    workflow_instance_id=str(instance.id),
                    contract_id=odcs_contract_id
                )
            except Contract.DoesNotExist:
                logger.warning(
                    "ODCS contract not found for rollback",
                    workflow_instance_id=str(instance.id),
                    contract_id=odcs_contract_id
                )

        return {"compensated": True}
```

**Workflow Execution**:

```python
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflows.product_creation import ProductCreationWorkflow

# Initialize workflow engine and registry
engine = WorkflowEngine()
registry = WorkflowRegistry()

# Register workflow and tasks
ProductCreationWorkflow.register_workflow(registry)
ProductCreationWorkflow.register_tasks(engine)

# Create workflow instance
input_data = {
    "original_raw": odps_raw,
    "original_format": "json",
    "tenant_id": tenant_id,
    "user_id": user_id
}

instance = engine.create_instance(
    workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
    input_data=input_data,
    tenant_id=tenant_id,
    created_by_id=user_id
)

# Start workflow execution
instance = engine.start_instance(str(instance.id))

# Execute workflow (runs all steps in order)
instance = engine.execute_instance(str(instance.id))

# Check workflow status
if instance.status == WorkflowStatus.COMPLETED:
    # Workflow succeeded
    odcs_contract_id = instance.state_data.get("odcs_contract_id")
    odps_contract_id = instance.state_data.get("odps_contract_id")
    # ... use results ...
elif instance.status == WorkflowStatus.FAILED:
    # Workflow failed - compensation executed automatically
    error_message = instance.error_message
    # ... handle failure ...
```

**Test Example**:

**Location**: `hub/apps/orchestration/workflows/tests/test_product_creation.py`

```python
from django.test import TestCase
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflows.product_creation import ProductCreationWorkflow
from hub.apps.orchestration.models import WorkflowStatus

class ProductCreationWorkflowTest(TestCase):
    """Tests for ProductCreationWorkflow."""

    def setUp(self):
        """Set up workflow engine and registry."""
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()

        # Register workflow and tasks
        ProductCreationWorkflow.register_workflow(self.registry)
        ProductCreationWorkflow.register_tasks(self.engine)

    def test_product_creation_workflow_success(self):
        """Test workflow orchestration pattern: Multi-step coordination."""
        # Setup: Prepare input data
        input_data = {
            "original_raw": self.valid_odps_raw,
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }

        # Execute: Create and run workflow
        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        instance = self.engine.start_instance(str(instance.id))
        instance = self.engine.execute_instance(str(instance.id))

        # Verify: Workflow completed successfully
        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)

        # Verify: All steps executed in order
        steps = instance.steps.all().order_by('step_index')
        self.assertEqual(len(steps), 11)  # All 11 steps

        # Verify: State data contains contract IDs
        self.assertIn("odcs_contract_id", instance.state_data)
        self.assertIn("odps_contract_id", instance.state_data)

        # Verify: Contracts were created
        from hub.apps.contracts.models import Contract
        odcs_contract = Contract.objects.get(
            id=instance.state_data["odcs_contract_id"]
        )
        odps_contract = Contract.objects.get(
            id=instance.state_data["odps_contract_id"]
        )

        self.assertIsNotNone(odcs_contract)
        self.assertIsNotNone(odps_contract)

    def test_product_creation_workflow_compensation(self):
        """Test workflow compensation: Rollback on failure."""
        # Setup: Create workflow with invalid data (will fail)
        input_data = {
            "original_raw": "invalid json",
            "original_format": "JSON",
            "tenant_id": str(self.tenant.id),
            "user_id": str(self.user.id)
        }

        # Execute: Run workflow (will fail)
        instance = self.engine.create_instance(
            workflow_name=ProductCreationWorkflow.WORKFLOW_NAME,
            input_data=input_data,
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )

        instance = self.engine.start_instance(str(instance.id))

        try:
            instance = self.engine.execute_instance(str(instance.id))
        except Exception:
            pass  # Expected to fail

        instance.refresh_from_db()

        # Verify: Workflow failed
        self.assertEqual(instance.status, WorkflowStatus.FAILED)

        # Verify: Compensation executed (no partial contracts created)
        from hub.apps.contracts.models import Contract
        contracts = Contract.objects.filter(
            tenant_id=self.tenant.id
        )
        self.assertEqual(contracts.count(), 0, "Compensation should rollback contracts")
```

**Key Characteristics**:
- ✅ Multi-step orchestration (11 steps in sequence)
- ✅ State management (state_data persists across steps)
- ✅ Dependency management (steps depend on previous steps)
- ✅ Compensation logic (automatic rollback on failure)
- ✅ Retry logic (transient failures retried automatically)
- ✅ Saga pattern (distributed transaction management)

---

## Anti-Patterns to Avoid

### 1. Synchronous Calls in Event Handlers

**❌ Anti-Pattern**:
```python
@event_subscriber('service_a', 'contract.created')
def handle_contract_created(event):
    # Synchronous call blocks event processing
    result = compliance_service.scan_contract(event["data"]["contract_id"])
    # If compliance service is slow, blocks all event processing
```

**✅ Correct Pattern**:
```python
@event_subscriber('service_a', 'contract.created')
def handle_contract_created(event):
    # Publish event for async processing
    publish_event("compliance.scan.requested", {
        "contract_id": event["data"]["contract_id"]
    })
```

### 2. Tight Coupling Through Direct Calls

**❌ Anti-Pattern**:
```python
# Service A directly calls Service B, C, D
def process_asset(asset_id):
    compliance_result = compliance_service.scan(asset_id)  # Direct call
    dq_result = dq_service.validate(asset_id)  # Direct call
    semantic_result = semantic_service.map(asset_id)  # Direct call
    # Tight coupling: if any service fails, entire operation fails
```

**✅ Correct Pattern**:
```python
# Use workflow orchestration for coordination
def process_asset(asset_id):
    workflow_engine.create_instance(
        workflow_name="asset_processing",
        input_data={"asset_id": asset_id}
    )
    # Workflow handles retries, compensation, and parallel execution
```

### 3. Ignoring Circuit Breakers

**❌ Anti-Pattern**:
```python
def call_external_service():
    # No circuit breaker protection
    response = requests.get("https://external-api.com/data")
    # If service is down, all requests fail immediately
    return response.json()
```

**✅ Correct Pattern**:
```python
from hub.apps.core.error_handling.error_recovery import CircuitBreaker

circuit_breaker = CircuitBreaker(
    service_name="external-api",
    failure_threshold=5,
    timeout_seconds=60
)

def call_external_service():
    # Protected by circuit breaker
    return circuit_breaker.call(lambda: requests.get("https://external-api.com/data").json())
```

### 4. Missing Retry Logic

**❌ Anti-Pattern**:
```python
def call_service():
    # No retry logic
    response = httpx.get("http://service:8080/api")
    response.raise_for_status()
    # Transient failures cause immediate failure
    return response.json()
```

**✅ Correct Pattern**:
```python
def call_service():
    # Retry with exponential backoff
    for attempt in range(3):
        try:
            response = httpx.get("http://service:8080/api")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500 and attempt < 2:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise
```

### 5. Blocking Operations in Workflows

**❌ Anti-Pattern**:
```python
def workflow_step(workflow_instance, step, input_data, state_data):
    # Blocking operation in workflow step
    result = long_running_service.process(data)  # Blocks for minutes
    # Workflow engine blocked, can't process other workflows
    return {"result": result}
```

**✅ Correct Pattern**:
```python
def workflow_step(workflow_instance, step, input_data, state_data):
    # Trigger async operation, update workflow state
    job_id = long_running_service.start_async_process(data)
    workflow_instance.state_data["job_id"] = job_id
    workflow_instance.status = WorkflowStatus.WAITING
    workflow_instance.save()

    # Subscribe to completion event
    @event_subscriber('workflow_engine', f'job.{job_id}.completed')
    def resume_workflow(event):
        workflow_engine.resume_instance(workflow_instance.id)

    return {"job_id": job_id}
```

### 6. Missing Distributed Tracing

**❌ Anti-Pattern**:
```python
def call_service():
    # No trace propagation
    response = httpx.get("http://service:8080/api")
    # Can't trace request across services
    return response.json()
```

**✅ Correct Pattern**:
```python
from hub.apps.api.middleware.trace_propagation import get_trace_headers

def call_service():
    # Propagate trace headers
    trace_headers = get_trace_headers()
    response = httpx.get(
        "http://service:8080/api",
        headers=trace_headers
    )
    # Request traced across all services
    return response.json()
```

### 7. Ignoring Dead Letter Queue

**❌ Anti-Pattern**:
```python
@event_subscriber('service', 'contract.created')
def handle_event(event):
    # No error handling, failed events lost
    process_contract(event["data"]["contract_id"])
```

**✅ Correct Pattern**:
```python
@event_subscriber('service', 'contract.created')
def handle_event(event):
    try:
        process_contract(event["data"]["contract_id"])
    except Exception as e:
        # Event automatically moved to DLQ
        logger.error(f"Failed to process event: {e}")
        # Monitor DLQ and replay failed events
        raise
```

### 8. Inconsistent Error Handling

**❌ Anti-Pattern**:
```python
# Different error handling in each service client
class ServiceA:
    def call(self):
        try:
            return requests.get(...).json()
        except:  # Too broad
            return None

class ServiceB:
    def call(self):
        return requests.get(...).json()  # No error handling
```

**✅ Correct Pattern**:
```python
# Consistent error handling pattern
class BaseServiceClient:
    def _request_with_retry(self, method, endpoint, **kwargs):
        # Standardized retry logic
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(self.backoff_factor * (2 ** attempt))
                    continue
                raise
```

---

## Summary

### Quick Reference

| Pattern | Use When | Avoid When |
|---------|----------|------------|
| **Direct Calls** | Immediate response needed, strong consistency | High throughput, eventual consistency acceptable |
| **Event-Driven** | Decoupled operations, high scalability | Immediate response required, strong consistency needed |
| **Workflow** | Complex multi-step, state management | Simple operations, low latency critical |

### Best Practices

1. **Always use circuit breakers** for external service calls
2. **Implement retry logic** with exponential backoff
3. **Propagate distributed tracing** headers across service boundaries
4. **Use event-driven patterns** for decoupled operations
5. **Use workflow orchestration** for complex multi-step operations
6. **Monitor Dead Letter Queue** and replay failed events
7. **Implement compensation logic** for distributed transactions
8. **Follow consistent error handling** patterns across all services

### Related Documentation

- [Event Bus Documentation](EVENT_BUS.md)
- [Workflow DSL Documentation](hub/apps/orchestration/WORKFLOW_DSL.md)
- [Error Handling Guide](ERROR_HANDLING.md)
- [Services Architecture](SERVICES_ARCHITECTURE.md)

---

**Last Updated**: 2025-01-15
**Version**: 1.0.0

