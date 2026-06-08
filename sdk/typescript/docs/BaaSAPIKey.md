# BaaSAPIKey

Serializer for BaaS APIKey model (read-only, no plaintext key). Also used for auth APIKey with tier.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**name** | **string** | API key name (for user identification) | [default to undefined]
**tier** | **string** |  | [optional] [readonly] [default to undefined]
**tenant_id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant_name** | **string** |  | [optional] [readonly] [default to undefined]
**user_id** | **string** |  | [optional] [readonly] [default to undefined]
**user_email** | **string** |  | [optional] [readonly] [default to undefined]
**expires_at** | **string** | Optional expiration timestamp | [optional] [default to undefined]
**revoked_at** | **string** | Revocation timestamp (null if active) | [optional] [readonly] [default to undefined]
**is_active** | **string** |  | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { BaaSAPIKey } from './api';

const instance: BaaSAPIKey = {
    id,
    name,
    tier,
    tenant_id,
    tenant_name,
    user_id,
    user_email,
    expires_at,
    revoked_at,
    is_active,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
