# ScheduledIngestionRun

Serializer for ScheduledIngestionRun model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**scheduled_ingestion** | **string** | Scheduled ingestion this run belongs to | [default to undefined]
**scheduled_ingestion_name** | **string** |  | [optional] [readonly] [default to undefined]
**status** | **string** | Run status: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED  * &#x60;PENDING&#x60; - Pending * &#x60;RUNNING&#x60; - Running * &#x60;COMPLETED&#x60; - Completed * &#x60;FAILED&#x60; - Failed * &#x60;CANCELLED&#x60; - Cancelled | [optional] [readonly] [default to undefined]
**started_at** | **string** | When run started | [optional] [readonly] [default to undefined]
**completed_at** | **string** | When run completed (success or failure) | [optional] [readonly] [default to undefined]
**prefect_flow_run_id** | **string** | Prefect flow run ID | [optional] [default to undefined]
**job_id** | **string** | Job ID (FK to jobs table) | [optional] [default to undefined]
**files_found** | **number** | Number of files found | [optional] [readonly] [default to undefined]
**files_processed** | **number** | Number of files successfully processed | [optional] [readonly] [default to undefined]
**files_failed** | **number** | Number of files that failed to process | [optional] [readonly] [default to undefined]
**datasets_created** | **number** | Number of datasets created | [optional] [readonly] [default to undefined]
**error_message** | **string** | Error message if run failed | [optional] [readonly] [default to undefined]
**result_json** | **any** | Run result data (files processed, datasets created, etc.) | [optional] [readonly] [default to undefined]
**dlq_sync_status** | **string** | Phase 72: DLQ sync status after run completion  * &#x60;PENDING&#x60; - Pending * &#x60;SYNCED&#x60; - Synced * &#x60;FAILED&#x60; - Failed | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { ScheduledIngestionRun } from './api';

const instance: ScheduledIngestionRun = {
    id,
    scheduled_ingestion,
    scheduled_ingestion_name,
    status,
    started_at,
    completed_at,
    prefect_flow_run_id,
    job_id,
    files_found,
    files_processed,
    files_failed,
    datasets_created,
    error_message,
    result_json,
    dlq_sync_status,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
