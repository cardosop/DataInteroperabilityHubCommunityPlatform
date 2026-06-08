# TenantCreate

Serializer for tenant creation

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**name** | **string** | Tenant name (unique per environment) | [default to undefined]
**slug** | **string** |  | [default to undefined]
**region** | **string** | Cloud region (e.g., us-east-1, eu-west-1) | [optional] [default to undefined]

## Example

```typescript
import { TenantCreate } from './api';

const instance: TenantCreate = {
    name,
    slug,
    region,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
