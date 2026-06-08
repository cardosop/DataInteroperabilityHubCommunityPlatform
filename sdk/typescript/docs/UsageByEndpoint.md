# UsageByEndpoint

Serializer for usage by endpoint

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**endpoint** | **string** |  | [default to undefined]
**method** | **string** |  | [default to undefined]
**total_requests** | **number** |  | [default to undefined]
**success_count** | **number** |  | [default to undefined]
**error_count** | **number** |  | [default to undefined]
**avg_response_time_ms** | **number** |  | [default to undefined]

## Example

```typescript
import { UsageByEndpoint } from './api';

const instance: UsageByEndpoint = {
    endpoint,
    method,
    total_requests,
    success_count,
    error_count,
    avg_response_time_ms,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
