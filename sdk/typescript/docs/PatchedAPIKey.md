# PatchedAPIKey

Serializer for API key (without sensitive data)

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**name** | **string** | Human-readable name for the API key | [optional] [default to undefined]
**scopes** | **any** | List of scopes (e.g., [\&#39;assets:read\&#39;, \&#39;assets:write\&#39;]) | [optional] [default to undefined]
**expires_at** | **string** | Expiration timestamp (null for non-expiring keys) | [optional] [default to undefined]
**last_used_at** | **string** | Last time this API key was used | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { PatchedAPIKey } from './api';

const instance: PatchedAPIKey = {
    id,
    name,
    scopes,
    expires_at,
    last_used_at,
    created_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
