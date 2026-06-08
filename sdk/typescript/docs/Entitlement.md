# Entitlement

Serializer for Entitlement model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant (consumer) that has access | [optional] [readonly] [default to undefined]
**listing** | **string** | Listing this entitlement is for | [default to undefined]
**asset** | **string** | Asset this entitlement grants access to | [default to undefined]
**order** | **string** | Order that created this entitlement | [optional] [default to undefined]
**status** | **string** | Entitlement status: ACTIVE, REVOKED, EXPIRED  * &#x60;ACTIVE&#x60; - Active * &#x60;REVOKED&#x60; - Revoked * &#x60;EXPIRED&#x60; - Expired | [optional] [default to undefined]
**granted_at** | **string** | When the entitlement was granted | [optional] [readonly] [default to undefined]
**revoked_at** | **string** | When the entitlement was revoked | [optional] [readonly] [default to undefined]
**expires_at** | **string** | When the entitlement expires (null for permanent access) | [optional] [default to undefined]
**metadata_json** | **any** | Entitlement metadata: license details, etc. | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]
**asset_name** | **string** |  | [optional] [readonly] [default to undefined]
**listing_title** | **string** |  | [optional] [readonly] [default to undefined]
**is_active** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { Entitlement } from './api';

const instance: Entitlement = {
    id,
    tenant,
    listing,
    asset,
    order,
    status,
    granted_at,
    revoked_at,
    expires_at,
    metadata_json,
    created_at,
    updated_at,
    asset_name,
    listing_title,
    is_active,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
