# WebhookDelivery

Serializer for WebhookDelivery model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**webhook** | **string** | Webhook subscription | [default to undefined]
**webhook_name** | **string** |  | [optional] [readonly] [default to undefined]
**webhook_url** | **string** |  | [optional] [readonly] [default to undefined]
**event_type** | **string** | Event type that triggered the delivery | [default to undefined]
**payload** | **any** | Webhook payload (event data) | [default to undefined]
**signature** | **string** | HMAC signature of the payload | [optional] [readonly] [default to undefined]
**status** | **string** | Delivery status  * &#x60;PENDING&#x60; - Pending * &#x60;SUCCESS&#x60; - Success * &#x60;FAILED&#x60; - Failed * &#x60;DEAD_LETTER&#x60; - Dead Letter | [optional] [readonly] [default to undefined]
**attempt_number** | **number** | Current attempt number (0-indexed) | [optional] [readonly] [default to undefined]
**http_status_code** | **number** | HTTP status code from delivery attempt | [optional] [readonly] [default to undefined]
**response_body** | **string** | Response body from delivery attempt | [optional] [readonly] [default to undefined]
**error_message** | **string** | Error message if delivery failed | [optional] [readonly] [default to undefined]
**delivered_at** | **string** | When delivery succeeded | [optional] [readonly] [default to undefined]
**next_retry_at** | **string** | When to retry delivery (if failed) | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { WebhookDelivery } from './api';

const instance: WebhookDelivery = {
    id,
    webhook,
    webhook_name,
    webhook_url,
    event_type,
    payload,
    signature,
    status,
    attempt_number,
    http_status_code,
    response_body,
    error_message,
    delivered_at,
    next_retry_at,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
