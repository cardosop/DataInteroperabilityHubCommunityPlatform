# Invoice

Serializer for Invoice model.  Hides stripe_invoice_id from non-admin users.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this invoice belongs to | [default to undefined]
**subscription** | **string** | Subscription this invoice is for | [optional] [default to undefined]
**subscription_status** | **string** |  | [optional] [readonly] [default to undefined]
**stripe_invoice_id** | **string** | Stripe invoice ID | [optional] [readonly] [default to undefined]
**amount_due** | **string** | Amount due (converted from cents) | [optional] [readonly] [default to undefined]
**amount_paid** | **string** | Amount paid (converted from cents) | [optional] [readonly] [default to undefined]
**currency** | **string** | ISO 4217 currency code (e.g., \&#39;usd\&#39;, \&#39;eur\&#39;) | [optional] [readonly] [default to undefined]
**status** | **string** | Invoice status  * &#x60;draft&#x60; - Draft * &#x60;open&#x60; - Open * &#x60;paid&#x60; - Paid * &#x60;uncollectible&#x60; - Uncollectible * &#x60;void&#x60; - Void | [optional] [readonly] [default to undefined]
**invoice_pdf_url** | **string** | URL to invoice PDF | [optional] [readonly] [default to undefined]
**hosted_invoice_url** | **string** | URL to hosted invoice page | [optional] [readonly] [default to undefined]
**period_start** | **string** | Start of billing period | [optional] [readonly] [default to undefined]
**period_end** | **string** | End of billing period | [optional] [readonly] [default to undefined]
**due_date** | **string** | Invoice due date | [optional] [readonly] [default to undefined]
**paid_at** | **string** | When invoice was paid | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { Invoice } from './api';

const instance: Invoice = {
    id,
    tenant,
    subscription,
    subscription_status,
    stripe_invoice_id,
    amount_due,
    amount_paid,
    currency,
    status,
    invoice_pdf_url,
    hosted_invoice_url,
    period_start,
    period_end,
    due_date,
    paid_at,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
