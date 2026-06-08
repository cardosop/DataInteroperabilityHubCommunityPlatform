# Tenant

Serializer for Tenant model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**name** | **string** | Tenant name (unique per environment) | [default to undefined]
**slug** | **string** | URL-safe tenant identifier | [default to undefined]
**status** | **string** | * &#x60;ACTIVE&#x60; - Active * &#x60;SUSPENDED&#x60; - Suspended * &#x60;DELETED&#x60; - Deleted | [optional] [readonly] [default to undefined]
**kyc_status** | **string** | * &#x60;UNVERIFIED&#x60; - Unverified * &#x60;PENDING_REVIEW&#x60; - Pending review * &#x60;VERIFIED&#x60; - Verified | [default to undefined]
**region** | **string** | Cloud region (e.g., us-east-1, eu-west-1) | [optional] [default to undefined]
**plan** | **string** | Subscription plan for this tenant | [optional] [default to undefined]
**deleted_at** | **string** | Timestamp when tenant was marked for deletion | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { Tenant } from './api';

const instance: Tenant = {
    id,
    name,
    slug,
    status,
    kyc_status,
    region,
    plan,
    deleted_at,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
