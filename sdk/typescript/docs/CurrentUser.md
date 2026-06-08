# CurrentUser

Serializer for current user information

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [default to undefined]
**email** | **string** |  | [default to undefined]
**name** | **string** |  | [default to undefined]
**tenant_id** | **string** |  | [default to undefined]
**roles** | **Array&lt;string&gt;** |  | [default to undefined]
**permissions** | **Array&lt;string&gt;** |  | [default to undefined]
**created_at** | **string** |  | [default to undefined]
**last_login_at** | **string** |  | [default to undefined]
**avatar** | **string** |  | [optional] [default to undefined]
**preferences** | **any** |  | [optional] [default to undefined]
**feature_tenant_switch_enabled** | **boolean** | When false, tenant switch UI and X-Tenant-Id are disabled. | [optional] [default to true]

## Example

```typescript
import { CurrentUser } from './api';

const instance: CurrentUser = {
    id,
    email,
    name,
    tenant_id,
    roles,
    permissions,
    created_at,
    last_login_at,
    avatar,
    preferences,
    feature_tenant_switch_enabled,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
