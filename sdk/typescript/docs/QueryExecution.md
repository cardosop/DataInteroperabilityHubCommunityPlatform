# QueryExecution

Serializer for QueryExecution model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** | Unique identifier for the query execution | [optional] [readonly] [default to undefined]
**virtual_dataset** | **string** | Virtual dataset ID | [optional] [readonly] [default to undefined]
**virtual_dataset_name** | **string** | Name of the virtual dataset | [optional] [readonly] [default to undefined]
**query** | **string** | Query text that was executed (may include parameter substitution) | [default to undefined]
**parameters** | **any** | Query parameters as JSON object (parameter name -&gt; value mapping) | [optional] [default to undefined]
**execution_mode** | **string** | Execution mode: SYNC, ASYNC, SCHEDULED, MANUAL, AUTOMATED  * &#x60;SYNC&#x60; - Synchronous * &#x60;ASYNC&#x60; - Asynchronous * &#x60;SCHEDULED&#x60; - Scheduled * &#x60;MANUAL&#x60; - Manual * &#x60;AUTOMATED&#x60; - Automated | [optional] [default to undefined]
**status** | **string** | Execution status: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED  * &#x60;PENDING&#x60; - Pending * &#x60;RUNNING&#x60; - Running * &#x60;COMPLETED&#x60; - Completed * &#x60;FAILED&#x60; - Failed * &#x60;CANCELLED&#x60; - Cancelled | [optional] [readonly] [default to undefined]
**started_at** | **string** | When the execution started | [optional] [readonly] [default to undefined]
**completed_at** | **string** | When the execution completed | [optional] [readonly] [default to undefined]
**result_cache_key** | **string** | Cache key for result storage (optional) | [optional] [readonly] [default to undefined]
**result_storage_path** | **string** | Path to stored result file (optional) | [optional] [readonly] [default to undefined]
**execution_log** | **any** | Execution logs as JSON array (log entries with timestamp, level, message) | [optional] [readonly] [default to undefined]
**metrics** | **any** | Execution metrics as JSON object (duration_ms, rows_processed, memory_used, etc.) | [optional] [readonly] [default to undefined]
**job** | **string** | Job record for async execution (null for sync executions) | [optional] [readonly] [default to undefined]
**created_at** | **string** | When the query execution was created | [optional] [readonly] [default to undefined]
**updated_at** | **string** | When the query execution was last updated | [optional] [readonly] [default to undefined]

## Example

```typescript
import { QueryExecution } from './api';

const instance: QueryExecution = {
    id,
    virtual_dataset,
    virtual_dataset_name,
    query,
    parameters,
    execution_mode,
    status,
    started_at,
    completed_at,
    result_cache_key,
    result_storage_path,
    execution_log,
    metrics,
    job,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
