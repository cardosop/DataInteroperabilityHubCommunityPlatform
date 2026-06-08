# QueryExecutionProgress

Serializer for query execution progress

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**execution_id** | **string** | Query execution ID | [default to undefined]
**status** | **string** | Current execution status | [default to undefined]
**progress_percentage** | **number** | Progress percentage (0-100) if available | [optional] [default to undefined]
**started_at** | **string** | When execution started | [optional] [default to undefined]
**completed_at** | **string** | When execution completed | [optional] [default to undefined]
**duration_seconds** | **number** | Execution duration in seconds | [optional] [default to undefined]
**metrics** | **{ [key: string]: any; }** | Execution metrics | [optional] [default to undefined]
**latest_logs** | **Array&lt;{ [key: string]: any; }&gt;** | Latest log entries | [optional] [default to undefined]

## Example

```typescript
import { QueryExecutionProgress } from './api';

const instance: QueryExecutionProgress = {
    execution_id,
    status,
    progress_percentage,
    started_at,
    completed_at,
    duration_seconds,
    metrics,
    latest_logs,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
