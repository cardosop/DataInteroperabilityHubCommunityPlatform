# PatchedScheduledExport

Serializer for ScheduledExport model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this scheduled export belongs to | [optional] [default to undefined]
**tenant_name** | **string** |  | [optional] [readonly] [default to undefined]
**name** | **string** | Scheduled export name (unique per tenant) | [optional] [default to undefined]
**schedule_config** | **any** | Schedule configuration (cron expression, timezone) | [optional] [default to undefined]
**destination_type** | **string** | Destination type: S3, GCS, AZURE_BLOB  * &#x60;S3&#x60; - Amazon S3 * &#x60;GCS&#x60; - Google Cloud Storage * &#x60;AZURE_BLOB&#x60; - Azure Blob Storage | [optional] [default to undefined]
**destination_config** | **any** | Destination configuration (connection details, credentials, paths) stored securely. Credentials are masked in API and logs. | [optional] [default to undefined]
**source_scope** | **any** | Source scope: asset_ids, dataset_ids, file_ids, or contract_id | [optional] [default to undefined]
**status** | **string** | Status: ACTIVE, PAUSED, ERROR  * &#x60;ACTIVE&#x60; - Active * &#x60;PAUSED&#x60; - Paused * &#x60;ERROR&#x60; - Error * &#x60;DELETED&#x60; - Deleted | [optional] [default to undefined]
**next_run_at** | **string** | Next scheduled run time (calculated based on schedule) | [optional] [readonly] [default to undefined]
**last_run_at** | **string** | Last run time | [optional] [readonly] [default to undefined]
**last_run_status** | **string** | Status of last run: RUNNING, COMPLETED, FAILED, CANCELLED  * &#x60;RUNNING&#x60; - Running * &#x60;COMPLETED&#x60; - Completed * &#x60;FAILED&#x60; - Failed * &#x60;CANCELLED&#x60; - Cancelled | [optional] [readonly] [default to undefined]
**prefect_deployment_id** | **string** | Prefect deployment ID returned by integration service | [optional] [readonly] [default to undefined]
**deployment_sync_status** | **string** | Prefect deployment sync status: SYNCED, PENDING, FAILED  * &#x60;SYNCED&#x60; - Synced * &#x60;PENDING&#x60; - Pending * &#x60;FAILED&#x60; - Failed | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { PatchedScheduledExport } from './api';

const instance: PatchedScheduledExport = {
    id,
    tenant,
    tenant_name,
    name,
    schedule_config,
    destination_type,
    destination_config,
    source_scope,
    status,
    next_run_at,
    last_run_at,
    last_run_status,
    prefect_deployment_id,
    deployment_sync_status,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
