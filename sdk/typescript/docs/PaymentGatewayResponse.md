# PaymentGatewayResponse

Serializer for payment gateway response

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**gateway_id** | **string** | Payment gateway ID | [default to undefined]
**webhook_url** | **string** | Linked webhook URL | [default to undefined]
**gateway_type** | **string** | Gateway type | [optional] [default to undefined]
**gateway_name** | **string** | Gateway name | [optional] [default to undefined]

## Example

```typescript
import { PaymentGatewayResponse } from './api';

const instance: PaymentGatewayResponse = {
    gateway_id,
    webhook_url,
    gateway_type,
    gateway_name,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
