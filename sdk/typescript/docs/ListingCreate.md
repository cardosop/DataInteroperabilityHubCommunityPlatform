# ListingCreate

Serializer for creating a listing

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**asset_id** | **string** | Asset to list | [default to undefined]
**title** | **string** | Public title for the listing | [default to undefined]
**short_description** | **string** | Brief description (1-2 sentences) | [default to undefined]
**long_description** | **string** | Detailed description | [optional] [default to undefined]
**pricing_model** | **string** | Pricing model: FREE, FREE_AUTO_APPROVE, REQUEST_APPROVAL  * &#x60;FREE&#x60; - Free * &#x60;FREE_AUTO_APPROVE&#x60; - Free (Auto-approve) * &#x60;REQUEST_APPROVAL&#x60; - Request Approval | [optional] [default to PricingModelEnum_Free]
**price_amount** | **number** | Price amount (required if pricing_model !&#x3D; FREE) | [optional] [default to undefined]
**currency** | **string** | Currency code (ISO 4217, e.g., USD, EUR). Required if pricing_model !&#x3D; FREE | [optional] [default to undefined]
**tags** | **Array&lt;string&gt;** | Tags for categorization | [optional] [default to undefined]
**domain** | **string** | Domain/category for the listing | [optional] [default to undefined]
**enable_stripe_gateway** | **boolean** | When true, enables Stripe for this listing (metadata x_odps.payment_gateways.stripe). | [optional] [default to false]

## Example

```typescript
import { ListingCreate } from './api';

const instance: ListingCreate = {
    asset_id,
    title,
    short_description,
    long_description,
    pricing_model,
    price_amount,
    currency,
    tags,
    domain,
    enable_stripe_gateway,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
