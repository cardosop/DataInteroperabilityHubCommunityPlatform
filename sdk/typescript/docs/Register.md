# Register

Serializer for user registration request

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**email** | **string** |  | [default to undefined]
**password** | **string** | Password must be at least 8 characters and contain uppercase, lowercase, and number | [default to undefined]
**name** | **string** | User full name | [default to undefined]
**tenant_id** | **string** | Tenant ID for multi-tenant registration (optional) | [optional] [default to undefined]

## Example

```typescript
import { Register } from './api';

const instance: Register = {
    email,
    password,
    name,
    tenant_id,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
