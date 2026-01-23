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

### ODPS Events

#### `odps.created`
Published when an ODPS contract is created.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `odps_version` (string)
- `status` (string)
- `normalization_status` (string)

#### `odps.updated`
Published when an ODPS contract is updated.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `odps.deleted`
Published when an ODPS contract is deleted.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `deleted_at` (ISO 8601 datetime)
- `reason` (string)

#### `odps.normalized`
Published when an ODPS contract normalization completes.

**Required Fields:**
- `contract_id` (UUID)
- `normalization_status` (string)

**Optional Fields:**
- `normalization_errors` (array of strings or null)
- `spec_version` (string)

#### `odps.linked`
Published when an ODPS contract is linked to ODCS.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `odcs_reference` (string)
- `link_type` (string)

#### `odps.unlinked`
Published when an ODPS contract is unlinked from ODCS.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `odcs_reference` (string)
- `reason` (string)

#### `odps.ref.resolved`
Published when ODPS $ref resolution completes successfully.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `resolved_refs_count` (integer)
- `duration_ms` (integer)

#### `odps.ref.failed`
Published when ODPS $ref resolution fails.

**Required Fields:**
- `contract_id` (UUID)
- `error_message` (string)

**Optional Fields:**
- `failed_refs` (array of strings)
- `error_details` (object)

#### `odps.export.started`
Published when ODPS export starts.

**Required Fields:**
- `contract_id` (UUID)
- `export_format` (string)

**Optional Fields:**
- `export_options` (object)

#### `odps.export.completed`
Published when ODPS export completes successfully.

**Required Fields:**
- `contract_id` (UUID)
- `export_format` (string)

**Optional Fields:**
- `export_size` (integer)
- `duration_ms` (integer)
- `export_file_id` (UUID)

#### `odps.export.failed`
Published when ODPS export fails.

**Required Fields:**
- `contract_id` (UUID)
- `export_format` (string)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)

#### `odps.workflow.started`
Published when an ODPS workflow starts.

**Required Fields:**
- `contract_id` (UUID)
- `workflow_name` (string)

**Optional Fields:**
- `workflow_version` (string)
- `input_data` (object)

#### `odps.workflow.completed`
Published when an ODPS workflow completes successfully.

**Required Fields:**
- `contract_id` (UUID)
- `workflow_name` (string)

**Optional Fields:**
- `output_data` (object)
- `duration_ms` (integer)

#### `odps.workflow.failed`
Published when an ODPS workflow fails.

**Required Fields:**
- `contract_id` (UUID)
- `workflow_name` (string)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `failed_step_index` (integer or null)

#### `odps.workflow.step.completed`
Published when an ODPS workflow step completes.

**Required Fields:**
- `contract_id` (UUID)
- `workflow_name` (string)
- `step_index` (integer)
- `step_name` (string)

**Optional Fields:**
- `output_data` (object)
- `duration_ms` (integer)

#### `odps.workflow.step.failed`
Published when an ODPS workflow step fails.

**Required Fields:**
- `contract_id` (UUID)
- `workflow_name` (string)
- `step_index` (integer)
- `step_name` (string)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `retry_count` (integer)

#### `odps.workflow.progress`
Published during ODPS workflow execution to report progress.

**Required Fields:**
- `contract_id` (UUID)
- `workflow_name` (string)
- `progress_percent` (number)

**Optional Fields:**
- `current_step` (string)
- `elapsed_time_ms` (integer)

#### `odps.creation.progress`
Published during ODPS contract creation to report progress.

**Required Fields:**
- `contract_id` (UUID)
- `progress_percent` (number)

**Optional Fields:**
- `current_step` (string)
- `elapsed_time_ms` (integer)

#### `odps.normalization.progress`
Published during ODPS normalization to report progress.

**Required Fields:**
- `contract_id` (UUID)
- `progress_percent` (number)

**Optional Fields:**
- `current_step` (string)
- `elapsed_time_ms` (integer)

#### `odps.ref.progress`
Published during ODPS $ref resolution to report progress.

**Required Fields:**
- `contract_id` (UUID)
- `progress_percent` (number)

**Optional Fields:**
- `resolved_refs_count` (integer)
- `total_refs_count` (integer)

#### `odps.linking.status`
Published when ODPS linking status changes.

**Required Fields:**
- `contract_id` (UUID)
- `linking_status` (string)

**Optional Fields:**
- `linked_refs_count` (integer)

#### `odps.export.progress`
Published during ODPS export to report progress.

**Required Fields:**
- `contract_id` (UUID)
- `export_format` (string)
- `progress_percent` (number)

**Optional Fields:**
- `current_step` (string)
- `elapsed_time_ms` (integer)

#### `odps.semantic.mapping.progress`
Published during ODPS semantic mapping to report progress.

**Required Fields:**
- `contract_id` (UUID)
- `progress_percent` (number)

**Optional Fields:**
- `mapped_entities_count` (integer)
- `total_entities_count` (integer)

#### `odps.semantic.mapped`
Published when ODPS semantic mapping completes.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `mapped_entities_count` (integer)
- `mapping_errors` (array of strings)

### Data Mesh Events

#### `domain.created`
Published when a data mesh domain is created.

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `name` (string)
- `status` (string)
- `owner_id` (UUID)

#### `domain.updated`
Published when a data mesh domain is updated.

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `domain.deleted`
Published when a data mesh domain is deleted.

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `deleted_at` (ISO 8601 datetime)
- `reason` (string)

#### `policy.applied`
Published when a policy is applied to a domain.

**Required Fields:**
- `policy_application_id` (UUID)
- `domain_id` (UUID)

**Optional Fields:**
- `policy_id` (UUID)
- `status` (string)

#### `policy.revoked`
Published when a policy is revoked from a domain.

**Required Fields:**
- `policy_application_id` (UUID)
- `domain_id` (UUID)

**Optional Fields:**
- `policy_id` (UUID)
- `reason` (string)

#### `mesh.compliance.checked`
Published when mesh compliance is checked.

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `compliance_status` (string)
- `violation_count` (integer)
- `checked_at` (ISO 8601 datetime)

#### `mesh.topology.updated`
Published when mesh topology is updated.

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `relationship_count` (integer)
- `topology_changes` (object)

#### `mesh.domain.created`
Published when a mesh domain is created (internal event).

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `name` (string)
- `status` (string)
- `owner_id` (UUID)

#### `mesh.domain.updated`
Published when a mesh domain is updated (internal event).

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `mesh.policy.applied`
Published when a mesh policy is applied (internal event).

**Required Fields:**
- `policy_application_id` (UUID)
- `domain_id` (UUID)

**Optional Fields:**
- `policy_id` (UUID)
- `status` (string)

#### `mesh.compliance.checked`
Published when mesh compliance is checked (internal event).

**Required Fields:**
- `domain_id` (UUID)

**Optional Fields:**
- `compliance_status` (string)
- `violation_count` (integer)
- `checked_at` (ISO 8601 datetime)

#### `mesh.health.status_changed`
Published when mesh health status changes.

**Required Fields:**
- `domain_id` (UUID)
- `health_status` (string)

**Optional Fields:**
- `previous_status` (string)
- `health_metrics` (object)

### Virtualization Events

#### `virtualization.dataset.created`
Published when a virtual dataset is created.

**Required Fields:**
- `virtual_dataset_id` (UUID)

**Optional Fields:**
- `name` (string)
- `query_type` (string)
- `status` (string)
- `version` (string)

#### `virtualization.dataset.updated`
Published when a virtual dataset is updated.

**Required Fields:**
- `virtual_dataset_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `virtualization.dataset.deleted`
Published when a virtual dataset is deleted.

**Required Fields:**
- `virtual_dataset_id` (UUID)

**Optional Fields:**
- `deleted_at` (ISO 8601 datetime)
- `reason` (string)

#### `virtualization.query.execution.started`
Published when a virtualization query execution starts.

**Required Fields:**
- `query_execution_id` (UUID)
- `virtual_dataset_id` (UUID)

**Optional Fields:**
- `execution_mode` (string)
- `started_at` (ISO 8601 datetime)

#### `virtualization.query.execution.progress`
Published during virtualization query execution to report progress.

**Required Fields:**
- `query_execution_id` (UUID)
- `virtual_dataset_id` (UUID)
- `progress_percent` (number)

**Optional Fields:**
- `current_step` (string)
- `elapsed_time_ms` (integer)
- `completed_steps` (integer)
- `total_steps` (integer)

#### `virtualization.query.execution.completed`
Published when a virtualization query execution completes successfully.

**Required Fields:**
- `query_execution_id` (UUID)
- `virtual_dataset_id` (UUID)

**Optional Fields:**
- `result_count` (integer)
- `duration_ms` (integer)
- `completed_at` (ISO 8601 datetime)

#### `virtualization.query.execution.failed`
Published when a virtualization query execution fails.

**Required Fields:**
- `query_execution_id` (UUID)
- `virtual_dataset_id` (UUID)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `duration_ms` (integer)
- `failed_at` (ISO 8601 datetime)

#### `virtualization.query.execution.cancelled`
Published when a virtualization query execution is cancelled.

**Required Fields:**
- `query_execution_id` (UUID)
- `virtual_dataset_id` (UUID)

**Optional Fields:**
- `cancelled_by` (UUID)
- `cancellation_reason` (string)
- `cancelled_at` (ISO 8601 datetime)

### File Events

#### `file.created`
Published when a file is created.

**Required Fields:**
- `file_id` (UUID)

**Optional Fields:**
- `name` (string)
- `content_type` (string)
- `size` (integer)
- `status` (string)
- `content_sha256` (string)

#### `file.updated`
Published when a file is updated.

**Required Fields:**
- `file_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `file.deleted`
Published when a file is deleted.

**Required Fields:**
- `file_id` (UUID)

**Optional Fields:**
- `deleted_at` (ISO 8601 datetime)
- `reason` (string)

#### `file.uploaded`
Published when a file is uploaded.

**Required Fields:**
- `file_id` (UUID)

**Optional Fields:**
- `file_size` (integer)
- `content_type` (string)
- `upload_duration_ms` (integer)
- `content_sha256` (string)

#### `file.downloaded`
Published when a file is downloaded.

**Required Fields:**
- `file_id` (UUID)

**Optional Fields:**
- `download_duration_ms` (integer)
- `download_size` (integer)

### Lineage Events

#### `lineage.updated`
Published when lineage is updated.

**Required Fields:**
- `contract_id` (UUID)

**Optional Fields:**
- `model_name` (string)
- `field_name` (string)
- `lineage_type` (string)
- `changes` (object)
- `relationship_count` (integer)

#### `lineage.relationship_added`
Published when a lineage relationship is added.

**Required Fields:**
- `contract_id` (UUID)
- `source_reference` (string)
- `target_reference` (string)

**Optional Fields:**
- `relationship_type` (string)
- `model_name` (string)
- `field_name` (string)

#### `lineage.relationship_removed`
Published when a lineage relationship is removed.

**Required Fields:**
- `contract_id` (UUID)
- `source_reference` (string)
- `target_reference` (string)

**Optional Fields:**
- `relationship_type` (string)
- `model_name` (string)
- `field_name` (string)

### Search Events

#### `search.query`
Published when a search query is executed.

**Required Fields:**
- `query` (string)

**Optional Fields:**
- `query_type` (string)
- `result_count` (integer)
- `duration_ms` (integer)

#### `search.index.updated`
Published when a search index is updated.

**Required Fields:**
- `index_name` (string)

**Optional Fields:**
- `document_count` (integer)
- `update_type` (string)

#### `search.index.rebuilt`
Published when a search index is rebuilt.

**Required Fields:**
- `index_name` (string)

**Optional Fields:**
- `document_count` (integer)
- `duration_ms` (integer)

### Payment Gateway Events

#### `payment.gateway.linked`
Published when a payment gateway is linked.

**Required Fields:**
- `gateway_id` (UUID)
- `gateway_type` (string)

**Optional Fields:**
- `linked_at` (ISO 8601 datetime)

#### `payment.gateway.unlinked`
Published when a payment gateway is unlinked.

**Required Fields:**
- `gateway_id` (UUID)

**Optional Fields:**
- `unlinked_at` (ISO 8601 datetime)
- `reason` (string)

#### `payment.gateway.webhook.received`
Published when a payment gateway webhook is received.

**Required Fields:**
- `gateway_id` (UUID)
- `webhook_type` (string)

**Optional Fields:**
- `webhook_data` (object)
- `received_at` (ISO 8601 datetime)

### Tenant Events

#### `tenant.created`
Published when a tenant is created.

**Required Fields:**
- `tenant_id` (UUID)

**Optional Fields:**
- `name` (string)
- `slug` (string)
- `status` (string)
- `kyc_status` (string)
- `region` (string)

#### `tenant.updated`
Published when a tenant is updated.

**Required Fields:**
- `tenant_id` (UUID)

**Optional Fields:**
- `changes` (object)
- `previous_status` (string)
- `new_status` (string)

#### `tenant.deleted`
Published when a tenant is deleted.

**Required Fields:**
- `tenant_id` (UUID)

**Optional Fields:**
- `deleted_at` (ISO 8601 datetime)
- `reason` (string)

#### `tenant.quota.changed`
Published when a tenant quota changes.

**Required Fields:**
- `tenant_id` (UUID)
- `quota_type` (string)
- `quota_field` (string)

**Optional Fields:**
- `previous_value` (any)
- `new_value` (any)

### Normalization Events

#### `normalization.started`
Published when normalization starts.

**Required Fields:**
- `contract_id` (UUID)
- `normalization_type` (string)

**Optional Fields:**
- `spec_version` (string)
- `source_format` (string)

#### `normalization.completed`
Published when normalization completes successfully.

**Required Fields:**
- `contract_id` (UUID)
- `normalization_status` (string)

**Optional Fields:**
- `normalization_errors` (array of strings)
- `normalization_warnings` (array of strings)
- `duration_ms` (integer)
- `spec_version` (string)

#### `normalization.failed`
Published when normalization fails.

**Required Fields:**
- `contract_id` (UUID)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `normalization_errors` (array of strings)
- `retry_count` (integer)
- `spec_version` (string)

### Payment Events

#### `payment.initiated`
Published when a payment is initiated.

**Required Fields:**
- `payment_id` (UUID)
- `order_id` (UUID)

**Optional Fields:**
- `amount` (number)
- `currency` (string)
- `gateway` (string)
- `payment_method` (string)

#### `payment.completed`
Published when a payment completes successfully.

**Required Fields:**
- `payment_id` (UUID)
- `order_id` (UUID)
- `status` (string)

**Optional Fields:**
- `amount` (number)
- `currency` (string)
- `gateway` (string)
- `gateway_transaction_id` (string)
- `processed_at` (ISO 8601 datetime)

#### `payment.failed`
Published when a payment fails.

**Required Fields:**
- `payment_id` (UUID)
- `order_id` (UUID)
- `error_message` (string)

**Optional Fields:**
- `error_details` (object)
- `amount` (number)
- `currency` (string)
- `gateway` (string)
- `failed_at` (ISO 8601 datetime)

#### `payment.refunded`
Published when a payment is refunded.

**Required Fields:**
- `payment_id` (UUID)
- `order_id` (UUID)

**Optional Fields:**
- `refund_amount` (number)
- `currency` (string)
- `gateway` (string)
- `gateway_refund_id` (string)
- `refund_reason` (string)
- `refunded_at` (ISO 8601 datetime)

### Observability Events

#### `observability.metric.recorded`
Published when a metric is recorded.

**Required Fields:**
- `metric_name` (string)

**Optional Fields:**
- `metric_value` (number)
- `metric_type` (string)
- `labels` (object)

#### `observability.trace.created`
Published when a trace is created.

**Required Fields:**
- `trace_id` (UUID)
- `span_id` (UUID)

**Optional Fields:**
- `operation_name` (string)
- `duration_ms` (number)
- `status` (string)
- `attributes` (object)

#### `observability.log.created`
Published when a log entry is created.

**Required Fields:**
- `message` (string)

**Optional Fields:**
- `log_level` (string)
- `logger_name` (string)
- `context` (object)

#### `observability.alert.triggered`
Published when an alert is triggered.

**Required Fields:**
- `alert_name` (string)
- `alert_severity` (string)

**Optional Fields:**
- `alert_message` (string)
- `metric_name` (string)
- `threshold_value` (number)
- `current_value` (number)

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

