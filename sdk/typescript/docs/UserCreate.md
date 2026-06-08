# UserCreate

Serializer for user creation

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**email** | **string** | User email address (unique across platform) | [default to undefined]
**display_name** | **string** | User display name | [optional] [default to undefined]
**tenant** | **string** | Tenant this user belongs to (null for platform admins) | [optional] [default to undefined]
**password** | **string** |  | [optional] [default to undefined]
**role_ids** | **Array&lt;string&gt;** | List of role IDs to assign to the user | [optional] [default to undefined]
**send_invitation** | **boolean** | Whether to send an invitation email to the user | [optional] [default to true]

## Example

```typescript
import { UserCreate } from './api';

const instance: UserCreate = {
    email,
    display_name,
    tenant,
    password,
    role_ids,
    send_invitation,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
