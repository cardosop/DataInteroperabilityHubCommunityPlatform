# PipelineExecution

Serializer for PipelineExecution model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** | Unique identifier for the execution | [optional] [readonly] [default to undefined]
**pipeline_id** | **string** |  | [optional] [readonly] [default to undefined]
**pipeline_name** | **string** |  | [optional] [readonly] [default to undefined]
**asset_id** | **string** |  | [optional] [readonly] [default to undefined]
**asset_name** | **string** |  | [optional] [readonly] [default to undefined]
**execution_mode** | **string** | * &#x60;SYNC&#x60; - Synchronous * &#x60;ASYNC&#x60; - Asynchronous * &#x60;SCHEDULED&#x60; - Scheduled * &#x60;MANUAL&#x60; - Manual * &#x60;AUTOMATED&#x60; - Automated | [optional] [readonly] [default to undefined]
**status** | **string** | * &#x60;PENDING&#x60; - Pending * &#x60;RUNNING&#x60; - Running * &#x60;COMPLETED&#x60; - Completed * &#x60;FAILED&#x60; - Failed * &#x60;CANCELLED&#x60; - Cancelled | [optional] [readonly] [default to undefined]
**started_at** | **string** | When the execution started | [optional] [readonly] [default to undefined]
**completed_at** | **string** | When the execution completed | [optional] [readonly] [default to undefined]
**result_asset_id** | **string** |  | [optional] [readonly] [default to undefined]
**result_asset_name** | **string** |  | [optional] [readonly] [default to undefined]
**job_id** | **string** |  | [optional] [readonly] [default to undefined]
**execution_log** | **any** | Execution log entries (JSON array of log messages, errors, warnings) | [optional] [readonly] [default to undefined]
**metrics** | **any** | Execution metrics (duration, throughput, items processed, etc.) | [optional] [readonly] [default to undefined]
**idempotency_key** | **string** | Idempotency key for retry safety (uses execution_id by default) | [optional] [readonly] [default to undefined]
**created_at** | **string** | When the execution record was created | [optional] [readonly] [default to undefined]
**updated_at** | **string** | When the execution record was last updated | [optional] [readonly] [default to undefined]
**duration_seconds** | **number** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { PipelineExecution } from './api';

const instance: PipelineExecution = {
    id,
    pipeline_id,
    pipeline_name,
    asset_id,
    asset_name,
    execution_mode,
    status,
    started_at,
    completed_at,
    result_asset_id,
    result_asset_name,
    job_id,
    execution_log,
    metrics,
    idempotency_key,
    created_at,
    updated_at,
    duration_seconds,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
