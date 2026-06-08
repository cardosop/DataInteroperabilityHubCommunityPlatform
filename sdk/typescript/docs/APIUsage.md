# APIUsage

Serializer for APIUsage model (supports auth_api_key or legacy api_key)

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**api_key_id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant_id** | **string** |  | [optional] [readonly] [default to undefined]
**user_id** | **string** |  | [optional] [readonly] [default to undefined]
**endpoint** | **string** | API endpoint path | [default to undefined]
**method** | **string** | HTTP method (GET, POST, PUT, DELETE, etc.) | [default to undefined]
**status_code** | **number** | HTTP status code | [default to undefined]
**response_time_ms** | **number** | Response time in milliseconds | [default to undefined]
**request_size_bytes** | **number** | Request size in bytes | [default to undefined]
**response_size_bytes** | **number** | Response size in bytes | [default to undefined]
**timestamp** | **string** | Request timestamp | [optional] [readonly] [default to undefined]

## Example

```typescript
import { APIUsage } from './api';

const instance: APIUsage = {
    id,
    api_key_id,
    tenant_id,
    user_id,
    endpoint,
    method,
    status_code,
    response_time_ms,
    request_size_bytes,
    response_size_bytes,
    timestamp,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
