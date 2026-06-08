# User

Serializer for User model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this user belongs to (null for platform admins) | [optional] [default to undefined]
**tenant_name** | **string** |  | [optional] [readonly] [default to undefined]
**email** | **string** | User email address (unique across platform) | [default to undefined]
**display_name** | **string** | User display name | [optional] [default to undefined]
**status** | **string** | * &#x60;ACTIVE&#x60; - Active * &#x60;INVITED&#x60; - Invited * &#x60;DISABLED&#x60; - Disabled * &#x60;SUSPENDED&#x60; - Suspended | [optional] [readonly] [default to undefined]
**is_platform_admin** | **boolean** | Platform-level admin privileges (transcends tenant boundaries) | [optional] [readonly] [default to undefined]
**roles** | **string** |  | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { User } from './api';

const instance: User = {
    id,
    tenant,
    tenant_name,
    email,
    display_name,
    status,
    is_platform_admin,
    roles,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
