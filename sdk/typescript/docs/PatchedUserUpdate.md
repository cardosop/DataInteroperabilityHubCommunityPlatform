# PatchedUserUpdate

Serializer for user update (roles, status, display_name). Admin only.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**display_name** | **string** | User display name | [optional] [default to undefined]
**status** | **string** | User status: ACTIVE, INVITED, or DISABLED  * &#x60;ACTIVE&#x60; - Active * &#x60;INVITED&#x60; - Invited * &#x60;DISABLED&#x60; - Disabled * &#x60;SUSPENDED&#x60; - Suspended | [optional] [default to undefined]
**role_ids** | **Array&lt;string&gt;** | List of role IDs to assign (replaces existing roles) | [optional] [default to undefined]

## Example

```typescript
import { PatchedUserUpdate } from './api';

const instance: PatchedUserUpdate = {
    display_name,
    status,
    role_ids,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
