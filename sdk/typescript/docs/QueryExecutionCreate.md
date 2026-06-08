# QueryExecutionCreate

Serializer for query execution creation with comprehensive validation

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**parameters** | **any** | Query parameters as JSON object | [optional] [default to undefined]
**execution_mode** | **string** | Execution mode: SYNC, ASYNC, SCHEDULED, MANUAL, AUTOMATED  * &#x60;SYNC&#x60; - Synchronous * &#x60;ASYNC&#x60; - Asynchronous * &#x60;SCHEDULED&#x60; - Scheduled * &#x60;MANUAL&#x60; - Manual * &#x60;AUTOMATED&#x60; - Automated | [optional] [default to undefined]
**force_async** | **boolean** | Force asynchronous execution even for small queries | [optional] [default to false]
**timeout_seconds** | **number** | Query timeout in seconds (default: 300 for sync, 3600 for async) | [optional] [default to undefined]

## Example

```typescript
import { QueryExecutionCreate } from './api';

const instance: QueryExecutionCreate = {
    parameters,
    execution_mode,
    force_async,
    timeout_seconds,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
