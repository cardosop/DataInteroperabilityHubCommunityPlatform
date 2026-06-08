# Order

Serializer for Order model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant (consumer) that requested this order | [optional] [readonly] [default to undefined]
**listing** | **string** | Listing this order is for | [default to undefined]
**status** | **string** | Order status: REQUESTED, APPROVED, REJECTED, CANCELLED, FULFILLED  * &#x60;REQUESTED&#x60; - Requested * &#x60;APPROVED&#x60; - Approved * &#x60;REJECTED&#x60; - Rejected * &#x60;CANCELLED&#x60; - Cancelled * &#x60;FULFILLED&#x60; - Fulfilled | [optional] [default to undefined]
**created_by** | **string** | User who created this order | [optional] [default to undefined]
**approved_by** | **string** | User who approved this order (null for auto-approved) | [optional] [default to undefined]
**metadata_json** | **any** | Order metadata: rejection_reason, etc. | [optional] [default to undefined]
**approved_at** | **string** | When the order was approved | [optional] [readonly] [default to undefined]
**rejected_at** | **string** | When the order was rejected | [optional] [readonly] [default to undefined]
**fulfilled_at** | **string** | When the order was fulfilled (entitlement created) | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]
**listing_title** | **string** |  | [optional] [readonly] [default to undefined]
**asset_id** | **string** |  | [optional] [readonly] [default to undefined]
**rejection_reason** | **string** |  | [optional] [readonly] [default to undefined]
**access_request_id** | **string** |  | [optional] [readonly] [default to undefined]
**entitlement_id** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { Order } from './api';

const instance: Order = {
    id,
    tenant,
    listing,
    status,
    created_by,
    approved_by,
    metadata_json,
    approved_at,
    rejected_at,
    fulfilled_at,
    created_at,
    updated_at,
    listing_title,
    asset_id,
    rejection_reason,
    access_request_id,
    entitlement_id,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
