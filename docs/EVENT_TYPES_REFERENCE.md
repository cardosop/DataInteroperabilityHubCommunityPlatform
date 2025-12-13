# Event Types Reference

## Overview

This document provides a comprehensive reference for all event types in the Data Interoperability Hub event system. All events follow a consistent schema structure and are validated before publishing.

## Event Schema Structure

All events follow this base structure:

```json
{
  "event_id": "uuid",
  "event_type": "domain.entity.action",
  "event_version": "1.0.0",
  "timestamp": "ISO 8601 datetime",
  "source": {
    "service": "service_name",
    "tenant_id": "uuid or null",
    "user_id": "uuid (optional)",
    "request_id": "string (optional)"
  },
  "data": {
    // Event-specific data
  },
  "metadata": {
    "correlation_id": "string (optional)",
    "causation_id": "uuid (optional)",
    "tags": ["string"] (optional)
  }
}
```

## Event Categories

### Contract Events

#### `contract.created`
Published when a contract is created.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `asset_id` (UUID)
- `status` (string)
- `original_format` (string)
- `original_spec_version` (string)

#### `contract.updated`
Published when a contract is updated.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `contract.deleted`
Published when a contract is deleted.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `deleted_at` (ISO 8601 datetime)
- `reason` (string)

#### `contract.validated`
Published when a contract validation completes.

**Required Fields:**
- `contract_id` (UUID)
- `validation_result` (boolean)

**Optional Fields:**
- `validation_errors` (array of strings)
- `validation_warnings` (array of strings)

#### `contract.normalized`
Published when a contract normalization completes.

**Required Fields:**
- `contract_id` (UUID)
- `normalization_status` (string)

**Optional Fields:**
- `normalization_errors` (array of strings or null)

### Asset Events

#### `asset.created`
Published when an asset is created.

**Required Fields:**
- `asset_id` (UUID)

**Optional Fields:**
- `name` (string)
- `domain` (string)
- `status` (string)
- `contract_id` (UUID)

#### `asset.updated`
Published when an asset is updated.

**Required Fields:**
- `asset_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `asset.activated`
Published when an asset is activated.

**Required Fields:**
- `asset_id` (UUID)

**Optional Fields:**
- `activation_reason` (string)
- `dq_status` (string)
- `compliance_status` (string)

#### `asset.published`
Published when an asset is published to marketplace.

**Required Fields:**
- `asset_id` (UUID)
- `marketplace_listing_id` (UUID)

**Optional Fields:**
- `pricing_model` (string)
- `license_type` (string)

#### `asset.retired`
Published when an asset is retired.

**Required Fields:**
- `asset_id` (UUID)

**Optional Fields:**
- `retirement_reason` (string)
- `retired_at` (ISO 8601 datetime)

### Dataset Events

#### `dataset.created`
Published when a dataset is created.

**Required Fields:**
- `dataset_id` (UUID)

**Optional Fields:**
- `asset_id` (UUID)
- `file_id` (UUID)
- `format` (string)
- `schema_inferred` (boolean)

#### `dataset.updated`
Published when a dataset is updated.

**Required Fields:**
- `dataset_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `file_id` (UUID)

#### `dataset.deleted`
Published when a dataset is deleted.

**Required Fields:**
- `dataset_id` (UUID)

**Optional Fields:**
- `deleted_at` (ISO 8601 datetime)
- `reason` (string)

#### `dataset.uploaded`
Published when a dataset file is uploaded.

**Required Fields:**
- `dataset_id` (UUID)
- `file_id` (UUID)

**Optional Fields:**
- `file_size` (integer)
- `file_format` (string)
- `upload_duration_ms` (integer)

### Ingestion Events

#### `ingestion.started`
Published when an ingestion process starts.

**Required Fields:**
- `ingestion_id` (UUID)
- `source_type` (string)

**Optional Fields:**
- `source_config` (object)
- `scheduled_ingestion_id` (UUID)

#### `ingestion.completed`
Published when an ingestion process completes.

**Required Fields:**
- `ingestion_id` (UUID)
- `files_processed` (integer)

**Optional Fields:**
- `files_succeeded` (integer)
- `files_failed` (integer)
- `duration_ms` (integer)
- `datasets_created` (integer)

#### `ingestion.failed`
Published when an ingestion process fails.

**Required Fields:**
- `ingestion_id` (UUID)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `retry_count` (integer)

#### `ingestion.file_processed`
Published when a single file is processed during ingestion.

**Required Fields:**
- `ingestion_id` (UUID)
- `file_id` (UUID)
- `status` (string)

**Optional Fields:**
- `dataset_id` (UUID)
- `error_message` (string)

### Quality Events

#### `quality.check.started`
Published when a quality check starts.

**Required Fields:**
- `quality_check_id` (UUID)
- `target_type` (string)
- `target_id` (UUID)

**Optional Fields:**
- `rules_count` (integer)

#### `quality.check.completed`
Published when a quality check completes.

**Required Fields:**
- `quality_check_id` (UUID)
- `overall_score` (number)

**Optional Fields:**
- `rules_passed` (integer)
- `rules_failed` (integer)
- `duration_ms` (integer)

#### `quality.check.failed`
Published when a quality check fails.

**Required Fields:**
- `quality_check_id` (UUID)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)

#### `quality.anomaly.detected`
Published when a quality anomaly is detected.

**Required Fields:**
- `quality_check_id` (UUID)
- `anomaly_type` (string)

**Optional Fields:**
- `anomaly_details` (object)
- `severity` (string)

### Compliance Events

#### `compliance.check.started`
Published when a compliance check starts.

**Required Fields:**
- `compliance_check_id` (UUID)
- `target_type` (string)
- `target_id` (UUID)

**Optional Fields:**
- `compliance_frameworks` (array of strings)

#### `compliance.check.completed`
Published when a compliance check completes.

**Required Fields:**
- `compliance_check_id` (UUID)
- `compliance_status` (string)

**Optional Fields:**
- `frameworks_passed` (array of strings)
- `frameworks_failed` (array of strings)
- `duration_ms` (integer)

#### `compliance.check.failed`
Published when a compliance check fails.

**Required Fields:**
- `compliance_check_id` (UUID)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)

#### `compliance.report.generated`
Published when a compliance report is generated.

**Required Fields:**
- `report_id` (UUID)
- `report_type` (string)

**Optional Fields:**
- `compliance_framework` (string)
- `report_format` (string)
- `generated_at` (ISO 8601 datetime)

### Version Events

#### `version.created`
Published when a version is created.

**Required Fields:**
- `version_id` (UUID)
- `resource_type` (string)
- `resource_id` (UUID)

**Optional Fields:**
- `version_number` (string)
- `version_type` (string)

#### `version.updated`
Published when a version is updated.

**Required Fields:**
- `version_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_version` (string)
- `new_version` (string)

#### `version.rolled_back`
Published when a version is rolled back.

**Required Fields:**
- `version_id` (UUID)
- `target_version` (string)

**Optional Fields:**
- `rollback_reason` (string)

### Access Events

#### `access.requested`
Published when an access request is created.

**Required Fields:**
- `access_request_id` (UUID)
- `resource_type` (string)
- `resource_id` (UUID)

**Optional Fields:**
- `requester_id` (UUID)
- `request_reason` (string)

#### `access.granted`
Published when access is granted.

**Required Fields:**
- `access_request_id` (UUID)
- `resource_type` (string)
- `resource_id` (UUID)

**Optional Fields:**
- `granted_by` (UUID)
- `granted_at` (ISO 8601 datetime)

#### `access.revoked`
Published when access is revoked.

**Required Fields:**
- `access_request_id` (UUID)
- `resource_type` (string)
- `resource_id` (UUID)

**Optional Fields:**
- `revoked_by` (UUID)
- `revoked_at` (ISO 8601 datetime)
- `revocation_reason` (string)

#### `access.certified`
Published when access is certified.

**Required Fields:**
- `access_request_id` (UUID)
- `certification_type` (string)

**Optional Fields:**
- `certified_by` (UUID)
- `certified_at` (ISO 8601 datetime)

### Marketplace Events

#### `marketplace.listing.published`
Published when a marketplace listing is published.

**Required Fields:**
- `listing_id` (UUID)
- `asset_id` (UUID)

**Optional Fields:**
- `pricing_model` (string)
- `published_at` (ISO 8601 datetime)

#### `marketplace.listing.unpublished`
Published when a marketplace listing is unpublished.

**Required Fields:**
- `listing_id` (UUID)

**Optional Fields:**
- `unpublished_at` (ISO 8601 datetime)
- `reason` (string)

#### `marketplace.order.created`
Published when a marketplace order is created.

**Required Fields:**
- `order_id` (UUID)
- `listing_id` (UUID)
- `buyer_id` (UUID)

**Optional Fields:**
- `order_amount` (number)
- `currency` (string)

#### `marketplace.order.approved`
Published when a marketplace order is approved.

**Required Fields:**
- `order_id` (UUID)

**Optional Fields:**
- `approved_by` (UUID)
- `approved_at` (ISO 8601 datetime)

#### `marketplace.order.rejected`
Published when a marketplace order is rejected.

**Required Fields:**
- `order_id` (UUID)
- `rejected_by` (UUID)
- `rejection_reason` (string)

**Optional Fields:**
- `rejected_at` (ISO 8601 datetime)

#### `marketplace.order.fulfilled`
Published when a marketplace order is fulfilled.

**Required Fields:**
- `order_id` (UUID)

**Optional Fields:**
- `fulfilled_at` (ISO 8601 datetime)
- `entitlement_id` (UUID)

#### `marketplace.entitlement.granted`
Published when a marketplace entitlement is granted.

**Required Fields:**
- `entitlement_id` (UUID)
- `order_id` (UUID)
- `user_id` (UUID)

**Optional Fields:**
- `granted_at` (ISO 8601 datetime)
- `expires_at` (ISO 8601 datetime or null)

#### `marketplace.entitlement.revoked`
Published when a marketplace entitlement is revoked.

**Required Fields:**
- `entitlement_id` (UUID)
- `revoked_by` (UUID)

**Optional Fields:**
- `revoked_at` (ISO 8601 datetime)
- `revocation_reason` (string)

### Workflow Events

#### `workflow.started`
Published when a workflow instance starts.

**Required Fields:**
- `workflow_instance_id` (UUID)
- `workflow_name` (string)

**Optional Fields:**
- `workflow_version` (string)
- `input_data` (object)

#### `workflow.completed`
Published when a workflow instance completes.

**Required Fields:**
- `workflow_instance_id` (UUID)
- `workflow_name` (string)

**Optional Fields:**
- `output_data` (object)
- `duration_ms` (integer)

#### `workflow.failed`
Published when a workflow instance fails.

**Required Fields:**
- `workflow_instance_id` (UUID)
- `workflow_name` (string)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `failed_step_index` (integer or null)

#### `workflow.cancelled`
Published when a workflow instance is cancelled.

**Required Fields:**
- `workflow_instance_id` (UUID)
- `workflow_name` (string)

**Optional Fields:**
- `cancelled_by` (UUID)
- `cancellation_reason` (string)

#### `workflow.step.completed`
Published when a workflow step completes.

**Required Fields:**
- `workflow_instance_id` (UUID)
- `step_index` (integer)
- `step_name` (string)

**Optional Fields:**
- `output_data` (object)
- `duration_ms` (integer)

#### `workflow.step.failed`
Published when a workflow step fails.

**Required Fields:**
- `workflow_instance_id` (UUID)
- `step_index` (integer)
- `step_name` (string)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `retry_count` (integer)

## Event Schema Versioning

All events use semantic versioning (e.g., `1.0.0`). The current version is `1.0.0`.

### Version Management

- **Current Version**: `1.0.0`
- **Supported Versions**: `["1.0.0"]`
- **Migration**: Events can be migrated between versions using `EventSchemaVersionManager`

## Usage Examples

### Publishing Events from Services

```python
from hub.apps.core.services.base import BaseService
from hub.apps.core.events.service_publishers import ContractEventPublisher

class ContractService(BaseService, ContractEventPublisher):
    def create_contract(self, ...):
        # ... create contract ...
        contract_id = contract.id
        
        # Publish event
        self.publish_contract_created(
            contract_id=str(contract_id),
            status="ACTIVE",
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        return contract
```

### Subscribing to Events

```python
from hub.apps.core.events.subscribers import WebhookSubscriber

# Create subscriber
subscriber = WebhookSubscriber(webhook_service=webhook_service)
subscriber.start()  # Start listening
```

### Using Decorator-Based Subscribers

```python
from hub.apps.core.events.subscriber import event_subscriber

@event_subscriber("contract.*")
def handle_contract_events(event):
    # Handle all contract events
    print(f"Received: {event['event_type']}")
```

## Event Validation

All events are validated before publishing:

1. **Base Schema Validation**: Validates event structure (event_id, event_type, timestamp, etc.)
2. **Event Type Schema Validation**: Validates event-specific data fields
3. **Type Validation**: Validates field types match schema

Invalid events are rejected with descriptive error messages.

## Best Practices

1. **Always include required fields**: Ensure all required fields are present in event data
2. **Use proper types**: Use correct data types (UUID strings, ISO 8601 datetimes, etc.)
3. **Include context**: Include tenant_id, user_id, and request_id when available
4. **Use correlation IDs**: Use correlation_id to track related events
5. **Handle failures gracefully**: Event publishing failures should not block business logic

## Event Flow

1. **Service publishes event** → Event data validated → Event persisted → Event published to Redis
2. **Subscribers receive event** → Event processed → Handler executed
3. **Failed events** → Retry logic → Dead letter queue if all retries fail

## Related Documentation

- [Event Bus Architecture](EVENT_BUS.md)
- [Event Bus Implementation Summary](EVENT_BUS_IMPLEMENTATION_SUMMARY.md)

