# ScheduledExportRun

Serializer for ScheduledExportRun model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**scheduled_export** | **string** | Scheduled export this run belongs to | [default to undefined]
**scheduled_export_name** | **string** |  | [optional] [readonly] [default to undefined]
**status** | **string** | Run status: RUNNING, COMPLETED, FAILED, CANCELLED  * &#x60;RUNNING&#x60; - Running * &#x60;COMPLETED&#x60; - Completed * &#x60;FAILED&#x60; - Failed * &#x60;CANCELLED&#x60; - Cancelled | [optional] [readonly] [default to undefined]
**items_found** | **number** | Number of items found for export | [optional] [readonly] [default to undefined]
**items_exported** | **number** | Number of items successfully exported | [optional] [readonly] [default to undefined]
**items_failed** | **number** | Number of items that failed to export | [optional] [readonly] [default to undefined]
**result_json** | **any** | Run result data (items exported, errors, etc.) | [optional] [readonly] [default to undefined]
**started_at** | **string** | When run started | [optional] [readonly] [default to undefined]
**completed_at** | **string** | When run completed (success or failure) | [optional] [readonly] [default to undefined]
**prefect_flow_run_id** | **string** | Prefect flow run ID | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { ScheduledExportRun } from './api';

const instance: ScheduledExportRun = {
    id,
    scheduled_export,
    scheduled_export_name,
    status,
    items_found,
    items_exported,
    items_failed,
    result_json,
    started_at,
    completed_at,
    prefect_flow_run_id,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
