# AccessCertification

Serializer for AccessCertification

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this certification belongs to | [optional] [readonly] [default to undefined]
**user** | **string** | User being certified | [default to undefined]
**asset** | **string** | Asset access being certified (nullable for user-level certification) | [optional] [default to undefined]
**dataset** | **string** | Dataset access being certified (nullable) | [optional] [default to undefined]
**certification_type** | **string** | Type of certification  * &#x60;USER_LEVEL&#x60; - User Level * &#x60;ASSET_LEVEL&#x60; - Asset Level * &#x60;DATASET_LEVEL&#x60; - Dataset Level | [default to undefined]
**status** | **string** | Certification status  * &#x60;PENDING&#x60; - Pending * &#x60;IN_PROGRESS&#x60; - In Progress * &#x60;APPROVED&#x60; - Approved * &#x60;REJECTED&#x60; - Rejected * &#x60;EXPIRED&#x60; - Expired | [optional] [default to undefined]
**reviewer** | **string** | User reviewing this certification | [optional] [default to undefined]
**review_notes** | **string** | Review notes from certifier | [optional] [default to undefined]
**expires_at** | **string** | Certification expiration date | [default to undefined]
**certified_at** | **string** | When certification was approved | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { AccessCertification } from './api';

const instance: AccessCertification = {
    id,
    tenant,
    user,
    asset,
    dataset,
    certification_type,
    status,
    reviewer,
    review_notes,
    expires_at,
    certified_at,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
