# PatchedDomain

Serializer for DataMeshDomain model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**name** | **string** | Domain name (unique per tenant) | [optional] [default to undefined]
**description** | **string** | Domain description | [optional] [default to undefined]
**owner** | **string** |  | [optional] [readonly] [default to undefined]
**owner_email** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this domain belongs to | [optional] [readonly] [default to undefined]
**tenant_name** | **string** |  | [optional] [readonly] [default to undefined]
**boundaries** | **any** |  | [optional] [default to undefined]
**capabilities** | **any** |  | [optional] [default to undefined]
**resource_quota** | **any** |  | [optional] [default to undefined]
**resource_usage** | **any** | Current resource usage as JSON (storage_gb_used, compute_hours_used, etc.) | [optional] [default to undefined]
**status** | **string** | * &#x60;ACTIVE&#x60; - Active * &#x60;INACTIVE&#x60; - Inactive * &#x60;ARCHIVED&#x60; - Archived | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { PatchedDomain } from './api';

const instance: PatchedDomain = {
    id,
    name,
    description,
    owner,
    owner_email,
    tenant,
    tenant_name,
    boundaries,
    capabilities,
    resource_quota,
    resource_usage,
    status,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
