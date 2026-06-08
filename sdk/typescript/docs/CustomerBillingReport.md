# CustomerBillingReport

Read-only serializer for CustomerBillingReport.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant_id** | **string** | Tenant that owns this report | [optional] [readonly] [default to undefined]
**api_key_id** | **string** | API key this report covers | [optional] [readonly] [default to undefined]
**customer_id** | **string** | Customer identifier (denormalized from API key) | [optional] [readonly] [default to undefined]
**customer_name** | **string** | Customer name (denormalized) | [optional] [readonly] [default to undefined]
**customer_email** | **string** | Customer billing email (denormalized) | [optional] [readonly] [default to undefined]
**period_start** | **string** | Billing period start | [optional] [readonly] [default to undefined]
**period_end** | **string** | Billing period end | [optional] [readonly] [default to undefined]
**total_requests** | **number** | Total API requests in period | [optional] [readonly] [default to undefined]
**billable_requests** | **number** | Billable requests (after deductions) | [optional] [readonly] [default to undefined]
**included_requests** | **number** | Requests included in flat fee | [optional] [readonly] [default to undefined]
**overage_requests** | **number** | Requests above included threshold | [optional] [readonly] [default to undefined]
**base_fee** | **string** | Monthly flat fee charged | [optional] [readonly] [default to undefined]
**overage_fee** | **string** | Fee for overage requests | [optional] [readonly] [default to undefined]
**total_amount** | **string** | Total amount due | [optional] [readonly] [default to undefined]
**currency** | **string** | ISO 4217 currency code | [optional] [readonly] [default to undefined]
**status** | **string** | Report lifecycle status  * &#x60;DRAFT&#x60; - Draft * &#x60;FINALIZED&#x60; - Finalized * &#x60;SENT&#x60; - Sent * &#x60;VOID&#x60; - Void | [optional] [readonly] [default to undefined]
**finalized_at** | **string** | When the report was finalized | [optional] [readonly] [default to undefined]
**sent_at** | **string** | When the report was emailed to customer | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { CustomerBillingReport } from './api';

const instance: CustomerBillingReport = {
    id,
    tenant_id,
    api_key_id,
    customer_id,
    customer_name,
    customer_email,
    period_start,
    period_end,
    total_requests,
    billable_requests,
    included_requests,
    overage_requests,
    base_fee,
    overage_fee,
    total_amount,
    currency,
    status,
    finalized_at,
    sent_at,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
