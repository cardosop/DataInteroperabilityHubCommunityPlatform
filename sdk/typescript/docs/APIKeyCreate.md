# APIKeyCreate

Serializer for API key creation

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**name** | **string** | Human-readable name for the API key | [default to undefined]
**scopes** | **Array&lt;string&gt;** | List of scopes (e.g., [\&#39;assets:read\&#39;, \&#39;assets:write\&#39;]) | [optional] [default to undefined]
**expires_in_days** | **number** | Number of days until expiration (null for non-expiring) | [optional] [default to undefined]

## Example

```typescript
import { APIKeyCreate } from './api';

const instance: APIKeyCreate = {
    name,
    scopes,
    expires_in_days,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
