# Role

Serializer for Role model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this role belongs to | [default to undefined]
**name** | **string** | Role name (e.g., TENANT_ADMIN, DATA_PROVIDER) | [default to undefined]
**description** | **string** | Role description | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { Role } from './api';

const instance: Role = {
    id,
    tenant,
    name,
    description,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
