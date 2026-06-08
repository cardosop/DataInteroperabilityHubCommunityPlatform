# PatchedTenantUpdate

Serializer for tenant update

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**name** | **string** | Tenant name (unique per environment) | [optional] [default to undefined]
**slug** | **string** | URL-safe tenant identifier | [optional] [default to undefined]
**kyc_status** | **string** | KYC verification status: UNVERIFIED, PENDING_REVIEW (submission with provider), or VERIFIED  * &#x60;UNVERIFIED&#x60; - Unverified * &#x60;PENDING_REVIEW&#x60; - Pending review * &#x60;VERIFIED&#x60; - Verified | [optional] [default to undefined]
**region** | **string** | Cloud region (e.g., us-east-1, eu-west-1) | [optional] [default to undefined]

## Example

```typescript
import { PatchedTenantUpdate } from './api';

const instance: PatchedTenantUpdate = {
    name,
    slug,
    kyc_status,
    region,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
