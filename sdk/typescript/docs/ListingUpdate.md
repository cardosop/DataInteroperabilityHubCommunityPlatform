# ListingUpdate

Serializer for updating a listing

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**title** | **string** |  | [optional] [default to undefined]
**short_description** | **string** |  | [optional] [default to undefined]
**long_description** | **string** |  | [optional] [default to undefined]
**pricing_model** | **string** | * &#x60;FREE&#x60; - Free * &#x60;FREE_AUTO_APPROVE&#x60; - Free (Auto-approve) * &#x60;REQUEST_APPROVAL&#x60; - Request Approval | [optional] [default to undefined]
**price_amount** | **number** |  | [optional] [default to undefined]
**currency** | **string** |  | [optional] [default to undefined]
**tags** | **Array&lt;string&gt;** |  | [optional] [default to undefined]
**domain** | **string** |  | [optional] [default to undefined]
**status** | **string** | * &#x60;DRAFT&#x60; - Draft * &#x60;PUBLISHED&#x60; - Published * &#x60;UNLISTED&#x60; - Unlisted * &#x60;DELETED&#x60; - Deleted | [optional] [default to undefined]
**enable_stripe_gateway** | **boolean** | When true, merges Stripe into x_odps.payment_gateways for this listing. | [optional] [default to false]
**force_publish** | **boolean** | PLATFORM_ADMIN bypass of compliance risk gate when publishing. | [optional] [default to false]

## Example

```typescript
import { ListingUpdate } from './api';

const instance: ListingUpdate = {
    title,
    short_description,
    long_description,
    pricing_model,
    price_amount,
    currency,
    tags,
    domain,
    status,
    enable_stripe_gateway,
    force_publish,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
