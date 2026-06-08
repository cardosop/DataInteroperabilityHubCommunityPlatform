# Subscription

Serializer for Subscription model.  Hides stripe_subscription_id and stripe_customer_id from non-admin users.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this subscription belongs to | [default to undefined]
**plan** | **string** | Plan this subscription is for | [default to undefined]
**plan_name** | **string** |  | [optional] [readonly] [default to undefined]
**plan_slug** | **string** |  | [optional] [readonly] [default to undefined]
**plan_tier** | **string** |  | [optional] [readonly] [default to undefined]
**category** | **string** | Plan category: BASE or ML_AI — denormalised from plan at creation time | [optional] [default to undefined]
**limits** | **string** |  | [optional] [readonly] [default to undefined]
**status** | **string** | Subscription status  * &#x60;ACTIVE&#x60; - Active * &#x60;PAST_DUE&#x60; - Past Due * &#x60;CANCELED&#x60; - Canceled * &#x60;TRIAL&#x60; - Trial * &#x60;INCOMPLETE&#x60; - Incomplete * &#x60;INCOMPLETE_EXPIRED&#x60; - Incomplete Expired * &#x60;UNPAID&#x60; - Unpaid | [optional] [default to undefined]
**stripe_subscription_id** | **string** | Stripe subscription ID (sub_...) | [optional] [readonly] [default to undefined]
**stripe_customer_id** | **string** | Stripe customer ID | [optional] [readonly] [default to undefined]
**current_period_start** | **string** | Start of current billing period | [optional] [readonly] [default to undefined]
**current_period_end** | **string** | End of current billing period | [optional] [readonly] [default to undefined]
**trial_end** | **string** | End of trial period (if applicable) | [optional] [readonly] [default to undefined]
**canceled_at** | **string** | When subscription was canceled | [optional] [readonly] [default to undefined]
**cancel_at_period_end** | **boolean** | Whether subscription will cancel at end of period | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { Subscription } from './api';

const instance: Subscription = {
    id,
    tenant,
    plan,
    plan_name,
    plan_slug,
    plan_tier,
    category,
    limits,
    status,
    stripe_subscription_id,
    stripe_customer_id,
    current_period_start,
    current_period_end,
    trial_end,
    canceled_at,
    cancel_at_period_end,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
