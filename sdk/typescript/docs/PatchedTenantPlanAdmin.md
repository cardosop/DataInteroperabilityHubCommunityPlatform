# PatchedTenantPlanAdmin

Serializer for admin CRUD on TenantPlan.  Validates limits_json against KNOWN_LIMIT_KEYS via the model\'s clean().

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**name** | **string** | Plan name (e.g., \&#39;Free Plan\&#39;, \&#39;Pro Plan\&#39;) | [optional] [default to undefined]
**slug** | **string** | URL-safe plan identifier (e.g., \&#39;free\&#39;, \&#39;pro\&#39;, \&#39;enterprise\&#39;) | [optional] [default to undefined]
**tier** | **string** | Plan tier: FREE, PRO, or ENTERPRISE  * &#x60;FREE&#x60; - Free * &#x60;PRO&#x60; - Pro * &#x60;ENTERPRISE&#x60; - Enterprise | [optional] [default to undefined]
**category** | **string** | Plan category: BASE (platform) or ML_AI (ML/AI package)  * &#x60;BASE&#x60; - Base Platform * &#x60;ML_AI&#x60; - ML / AI | [optional] [default to undefined]
**order** | **number** | Tier ordering for upgrade/downgrade validation (FREE&#x3D;0, PRO&#x3D;1, ENTERPRISE&#x3D;2) | [optional] [default to undefined]
**limits_json** | **any** | Plan limits as JSON (e.g., {\&#39;max_assets\&#39;: 10, \&#39;max_api_calls_per_month\&#39;: 10000}) | [optional] [default to undefined]
**is_active** | **boolean** | Whether this plan is currently active and available for subscription | [optional] [default to undefined]
**price_amount_cents** | **number** | Price amount in cents (e.g., 2999 &#x3D; $29.99). 0 for free plans. | [optional] [default to undefined]
**price_currency** | **string** | ISO 4217 currency code (e.g., \&#39;usd\&#39;, \&#39;eur\&#39;, \&#39;brl\&#39;) | [optional] [default to undefined]
**billing_interval** | **string** | Billing interval for recurring subscriptions  * &#x60;month&#x60; - Monthly * &#x60;year&#x60; - Yearly | [optional] [default to undefined]
**stripe_product_id** | **string** | Stripe Product ID (prod_...) | [optional] [default to undefined]
**stripe_price_id** | **string** | Stripe Price ID (price_...) | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { PatchedTenantPlanAdmin } from './api';

const instance: PatchedTenantPlanAdmin = {
    id,
    name,
    slug,
    tier,
    category,
    order,
    limits_json,
    is_active,
    price_amount_cents,
    price_currency,
    billing_interval,
    stripe_product_id,
    stripe_price_id,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
