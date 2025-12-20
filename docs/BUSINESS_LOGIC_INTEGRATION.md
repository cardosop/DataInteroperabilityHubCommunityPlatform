# Business Logic Integration Guide

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

---

## Overview

This document describes how business logic is integrated across all features of the Data Interoperability Hub. The platform uses a comprehensive integration layer that coordinates features through workflows, service layers, events, and business rules.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Service Layer Coordination](#service-layer-coordination)
3. [Workflow Integration](#workflow-integration)
4. [Event-Driven Coordination](#event-driven-coordination)
5. [Business Rules Framework](#business-rules-framework)
6. [Compensation Logic](#compensation-logic)
7. [Data Consistency](#data-consistency)
8. [Frontend Integration](#frontend-integration)
9. [Best Practices](#best-practices)

---

## Architecture

### Integration Layer Components

```
┌─────────────────────────────────────────────────────────┐
│              Business Logic Integration Layer            │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Service    │  │   Workflow   │  │    Event     │ │
│  │    Layer     │  │   Engine     │  │     Bus      │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                  │                  │         │
│         └──────────────────┼──────────────────┘         │
│                            │                              │
│                   ┌────────▼────────┐                    │
│                   │ Business Rules  │                    │
│                   │    Framework    │                    │
│                   └─────────────────┘                    │
│                                                           │
└───────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Features    │    │  Features    │    │  Features    │
│  (AI/ML)     │    │(Transformation)│  │  (Social)   │
└──────────────┘    └──────────────┘    └──────────────┘
```

---

## Service Layer Coordination

### Service Layer Pattern

All business logic is coordinated through service layer classes that extend `BaseService`:

#### BaseService

```python
from hub.apps.core.services.base import BaseService

class MyService(BaseService):
    service_name = "my_service"
    
    def do_something(self, tenant_id: str, data: dict):
        # Business logic here
        # Publish events
        # Return result
        pass
```

#### Service Responsibilities

1. **Business Logic Coordination**: Coordinate operations across features
2. **Event Publishing**: Publish events for asynchronous coordination
3. **Transaction Management**: Manage transaction boundaries
4. **Error Handling**: Handle errors consistently
5. **Audit Logging**: Log all operations

### Service Classes

#### TransformationService

**Location**: `hub/apps/transformation/services.py`

**Responsibilities**:
- Coordinate pipeline execution with asset lifecycle
- Manage pipeline-to-asset relationships
- Handle pipeline result synchronization
- Validate pipeline compatibility with assets

**Example**:
```python
class TransformationService(BaseService):
    service_name = "transformation_service"
    
    def execute_pipeline(self, pipeline_id: str, asset_id: str):
        # Validate compatibility
        # Execute pipeline
        # Sync results with asset
        # Publish events
        pass
```

#### AIService

**Location**: `hub/apps/ai/services.py`

**Responsibilities**:
- Coordinate ML operations with workflows
- Manage ML model lifecycle
- Handle ML result validation
- Coordinate schema matching with contract creation

#### SocialService

**Location**: `hub/apps/social/services.py`

**Responsibilities**:
- Coordinate ratings/reviews with asset updates
- Manage review moderation workflows
- Handle social feature events
- Coordinate activity feeds with asset operations

#### MarketplaceService

**Location**: `hub/apps/marketplace/services.py`

**Responsibilities**:
- Coordinate publishing with transformation/quality
- Manage purchase workflows
- Handle pricing model validation
- Coordinate marketplace events with asset updates

#### DataMeshService

**Location**: `hub/apps/mesh/services.py`

**Responsibilities**:
- Coordinate domain operations
- Manage domain-to-asset relationships
- Handle federated governance
- Coordinate mesh topology updates

---

## Workflow Integration

### Workflow Engine

All multi-step operations are orchestrated through the workflow engine:

```python
from hub.apps.orchestration.workflow_engine import WorkflowEngine

engine = WorkflowEngine()
instance = engine.create_instance(
    workflow_name="asset_creation",
    input_data={"asset_id": "..."},
    tenant_id="...",
)
engine.start_instance(instance.id)
```

### Extended Workflows

#### AssetCreationWorkflow (Extended)

**New Steps**:
- AI schema matching
- Auto-classification
- ML-based quality checks

**DSL Example**:
```json
{
  "version": "1.0.0",
  "steps": [
    {"name": "create_asset", "type": "task", "task": "asset_creation.create_asset"},
    {"name": "ai_schema_matching", "type": "task", "task": "ai.schema_matching"},
    {"name": "auto_classification", "type": "task", "task": "ai.auto_classification"},
    {"name": "ml_quality_check", "type": "task", "task": "ai.ml_quality_check"}
  ]
}
```

#### TransformationPipelineWorkflow

**Steps**:
- Pipeline validation
- Pipeline execution
- Result synchronization
- Compensation on failure

#### MarketplacePublishingWorkflow

**Steps**:
- Transformation validation
- Quality check
- Pricing validation
- Listing creation

#### SocialFeatureWorkflow

**Steps**:
- Review validation
- Asset quality score update
- Notification

#### DataMeshWorkflow

**Steps**:
- Domain creation
- Asset ownership update
- Policy application

---

## Event-Driven Coordination

### Event Publishers

Services publish events for asynchronous coordination:

```python
from hub.apps.core.events.service_publishers import EventPublisher

class TransformationEventPublisher(EventPublisher):
    def publish_pipeline_completed(self, pipeline_id: str, result: dict):
        self.publish(
            event_type="transformation.pipeline_completed",
            data={"pipeline_id": pipeline_id, "result": result}
        )
```

### Event Handlers

Event handlers subscribe to events and trigger workflows:

```python
@event_handler("transformation.pipeline_completed")
def handle_pipeline_completed(event):
    # Update asset with pipeline results
    # Trigger asset update workflow
    pass
```

### Event Types

#### Transformation Events
- `transformation.pipeline_started`
- `transformation.pipeline_completed`
- `transformation.pipeline_failed`

#### AI/ML Events
- `ai.schema_matching_completed`
- `ai.classification_completed`
- `ai.recommendation_updated`

#### Social Events
- `social.review_created`
- `social.rating_updated`
- `social.comment_created`

#### Marketplace Events
- `marketplace.purchase_completed`
- `marketplace.pricing_changed`
- `marketplace.listing_updated`

#### Data Mesh Events
- `mesh.domain_created`
- `mesh.policy_applied`
- `mesh.topology_updated`

---

## Business Rules Framework

### Business Rules Base Class

```python
from hub.apps.core.business_rules.base import BusinessRules

class TransformationBusinessRules(BusinessRules):
    def validate_pipeline_compatibility(self, pipeline: Pipeline, asset: Asset):
        # Validate schema compatibility
        # Validate data type compatibility
        # Return validation result
        pass
```

### Rule Validation

Rules are validated in service layer:

```python
class TransformationService(BaseService):
    def execute_pipeline(self, pipeline_id: str, asset_id: str):
        # Validate using business rules
        rules = TransformationBusinessRules()
        validation = rules.validate_pipeline_compatibility(pipeline, asset)
        if not validation.is_valid:
            raise ValidationError(validation.errors)
        # Execute pipeline
        pass
```

### Cross-Feature Validation

```python
class CrossFeatureBusinessRules(BusinessRules):
    def validate_transformation_asset_compatibility(self, pipeline, asset):
        # Cross-feature validation logic
        pass
    
    def validate_ai_contract_alignment(self, schema_matching, contract):
        # Cross-feature validation logic
        pass
```

---

## Compensation Logic

### Compensation Pattern (Saga)

Workflows define compensation for rollback:

```json
{
  "version": "1.0.0",
  "compensation": {"enabled": true},
  "steps": [
    {
      "name": "create_resource",
      "type": "task",
      "task": "create_resource_task",
      "compensation": {
        "type": "task",
        "task": "delete_resource_task"
      }
    }
  ]
}
```

### Compensation Execution

Compensation is executed automatically on failure:

```python
# Workflow engine automatically executes compensation
# when a step fails and compensation is enabled
```

---

## Data Consistency

### Consistency Service

```python
from hub.apps.core.consistency.service import ConsistencyService

class ConsistencyService:
    def maintain_transformation_asset_consistency(self, pipeline_id: str, asset_id: str):
        # Sync pipeline results with asset
        # Validate consistency
        # Report inconsistencies
        pass
```

### Event-Driven Consistency

Consistency is maintained through event handlers:

```python
@event_handler("transformation.pipeline_completed")
def maintain_consistency(event):
    consistency_service = ConsistencyService()
    consistency_service.maintain_transformation_asset_consistency(
        event.data["pipeline_id"],
        event.data["asset_id"]
    )
```

### Scheduled Consistency Checks

```python
# Scheduled job runs consistency checks
@periodic_task(run_every=timedelta(hours=1))
def check_consistency():
    consistency_service = ConsistencyService()
    consistency_service.validate_all_consistency()
```

---

## Frontend Integration

### Workflow Progress Tracking

Frontend tracks workflow progress via React Query and WebSocket:

```typescript
import { useWorkflowProgress } from '@/hooks/useWorkflowProgress';

function TransformationPipelineProgress({ pipelineId }: { pipelineId: string }) {
  const { workflow, progress, currentStep, error } = useWorkflowProgress(
    'transformation_pipeline',
    pipelineId
  );

  return (
    <WorkflowProgress
      workflow={workflow}
      progress={progress}
      currentStep={currentStep}
      error={error}
    />
  );
}
```

### State Synchronization

Frontend state is synchronized with backend via WebSocket:

```typescript
import { useWebSocket } from '@/hooks/useWebSocket';

function useWorkflowUpdates(workflowName: string, instanceId: string) {
  const { data, queryClient } = useWebSocket(`workflow.${workflowName}.${instanceId}`);

  useEffect(() => {
    if (data) {
      queryClient.setQueryData(
        ['workflow', workflowName, instanceId],
        data
      );
    }
  }, [data, workflowName, instanceId, queryClient]);
}
```

---

## Best Practices

### Service Layer

1. **Single Responsibility**: Each service has a clear responsibility
2. **Dependency Injection**: Services use dependency injection
3. **Event Publishing**: Services publish events for coordination
4. **Error Handling**: Services handle errors consistently
5. **Transaction Management**: Services manage transaction boundaries

### Workflow Integration

1. **Workflow DSL**: Use workflow DSL for workflow definitions
2. **Compensation**: Always define compensation for critical operations
3. **State Management**: Use workflow state for multi-step operations
4. **Error Handling**: Handle workflow failures gracefully
5. **Progress Tracking**: Track workflow progress for user experience

### Event-Driven Coordination

1. **Event Schema**: Define event schemas clearly
2. **Event Versioning**: Version events for backward compatibility
3. **Event Correlation**: Track event correlation for debugging
4. **Event Replay**: Support event replay for recovery
5. **Event Monitoring**: Monitor event processing

### Business Rules

1. **Centralized Rules**: Keep rules in centralized framework
2. **Rule Testing**: Test rules independently
3. **Rule Configuration**: Make rules configurable per tenant
4. **Rule Documentation**: Document all business rules
5. **Rule Validation**: Validate rules at service layer

### Data Consistency

1. **Eventual Consistency**: Use eventual consistency model
2. **Consistency Validation**: Validate consistency regularly
3. **Consistency Metrics**: Track consistency metrics
4. **Consistency Monitoring**: Monitor consistency issues
5. **Consistency Recovery**: Recover from consistency issues

---

**Last Updated**: 2025-12-13

