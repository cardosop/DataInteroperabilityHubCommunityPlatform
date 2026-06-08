# Listing

Serializer for Listing model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant (provider) that owns this listing | [optional] [readonly] [default to undefined]
**asset** | **string** | Asset being listed (null for orphaned/listings without asset edge case) | [optional] [default to undefined]
**status** | **string** | Listing status: DRAFT, PUBLISHED, UNLISTED, DELETED  * &#x60;DRAFT&#x60; - Draft * &#x60;PUBLISHED&#x60; - Published * &#x60;UNLISTED&#x60; - Unlisted * &#x60;DELETED&#x60; - Deleted | [optional] [default to undefined]
**pricing_model** | **string** | Pricing model: FREE, FREE_AUTO_APPROVE, REQUEST_APPROVAL  * &#x60;FREE&#x60; - Free * &#x60;FREE_AUTO_APPROVE&#x60; - Free (Auto-approve) * &#x60;REQUEST_APPROVAL&#x60; - Request Approval | [optional] [default to undefined]
**metadata_json** | **any** | Listing metadata: title, description, price, currency, tags, domain, etc. | [optional] [default to undefined]
**published_at** | **string** | When the listing was published | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]
**title** | **string** |  | [optional] [readonly] [default to undefined]
**description** | **string** |  | [optional] [readonly] [default to undefined]
**short_description** | **string** |  | [optional] [readonly] [default to undefined]
**long_description** | **string** |  | [optional] [readonly] [default to undefined]
**price_amount** | **string** |  | [optional] [readonly] [default to undefined]
**currency** | **string** |  | [optional] [readonly] [default to undefined]
**tags** | **string** |  | [optional] [readonly] [default to undefined]
**domain** | **string** |  | [optional] [readonly] [default to undefined]
**latest_compliance_run** | **string** | Latest SUCCEEDED compliance run for the listing\&#39;s asset (Phase 231.3). | [optional] [readonly] [default to undefined]

## Example

```typescript
import { Listing } from './api';

const instance: Listing = {
    id,
    tenant,
    asset,
    status,
    pricing_model,
    metadata_json,
    published_at,
    created_at,
    updated_at,
    title,
    description,
    short_description,
    long_description,
    price_amount,
    currency,
    tags,
    domain,
    latest_compliance_run,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
