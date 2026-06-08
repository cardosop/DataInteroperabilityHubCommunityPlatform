# QueryExecutionCancelResponse

Serializer for query execution cancel response

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**execution_id** | **string** | Query execution ID | [default to undefined]
**status** | **string** | New execution status | [default to undefined]
**message** | **string** | Cancellation message | [default to undefined]

## Example

```typescript
import { QueryExecutionCancelResponse } from './api';

const instance: QueryExecutionCancelResponse = {
    execution_id,
    status,
    message,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
