# PaymentGatewayLinkWebhook

Serializer for linking webhook URL to payment gateway

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**contract_id** | **string** | ODPS contract ID | [default to undefined]
**gateway_id** | **string** | Payment gateway ID (e.g., \&#39;stripe\&#39;, \&#39;paypal\&#39;) | [default to undefined]
**webhook_url** | **string** | Webhook/callback URL to link | [default to undefined]
**validate** | **boolean** | Whether to validate the webhook URL (default: true) | [optional] [default to true]

## Example

```typescript
import { PaymentGatewayLinkWebhook } from './api';

const instance: PaymentGatewayLinkWebhook = {
    contract_id,
    gateway_id,
    webhook_url,
    validate,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
