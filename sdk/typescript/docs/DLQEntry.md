# DLQEntry

Serializer for Dead Letter Queue entry.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**event_type** | **string** | Event type | [optional] [readonly] [default to undefined]
**subscriber** | **string** | Subscriber that failed | [optional] [readonly] [default to undefined]
**error_message** | **string** | Error message | [optional] [readonly] [default to undefined]
**error_details** | **any** | Error details (stack trace, etc.) | [optional] [readonly] [default to undefined]
**retry_count** | **number** | Number of retries attempted | [optional] [readonly] [default to undefined]
**last_attempt_at** | **string** | Last retry attempt timestamp | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**resolved_at** | **string** | When issue was resolved | [optional] [readonly] [default to undefined]
**resolved_by** | **string** | User who resolved | [optional] [readonly] [default to undefined]

## Example

```typescript
import { DLQEntry } from './api';

const instance: DLQEntry = {
    id,
    event_type,
    subscriber,
    error_message,
    error_details,
    retry_count,
    last_attempt_at,
    created_at,
    resolved_at,
    resolved_by,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
