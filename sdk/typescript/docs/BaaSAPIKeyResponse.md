# BaaSAPIKeyResponse

Serializer for BaaS API key creation response (includes plaintext key)

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [default to undefined]
**name** | **string** |  | [default to undefined]
**api_key** | **string** | Plaintext API key (shown only once) | [default to undefined]
**tier** | **string** |  | [default to undefined]
**expires_at** | **string** |  | [default to undefined]
**created_at** | **string** |  | [default to undefined]

## Example

```typescript
import { BaaSAPIKeyResponse } from './api';

const instance: BaaSAPIKeyResponse = {
    id,
    name,
    api_key,
    tier,
    expires_at,
    created_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
