# Webhook

Serializer for Webhook model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**name** | **string** | Webhook name/description | [default to undefined]
**url** | **string** | Webhook delivery URL | [default to undefined]
**secret** | **string** | Webhook secret for HMAC signature | [default to undefined]
**event_types** | **any** | List of event types to subscribe to | [optional] [default to undefined]
**status** | **string** | Webhook status  * &#x60;ACTIVE&#x60; - Active * &#x60;PAUSED&#x60; - Paused * &#x60;DISABLED&#x60; - Disabled | [optional] [default to undefined]
**max_retries** | **number** | Maximum number of delivery retries | [optional] [default to undefined]
**retry_intervals** | **any** | Retry intervals in seconds: [1, 5, 30, 300, 1800] | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { Webhook } from './api';

const instance: Webhook = {
    id,
    name,
    url,
    secret,
    event_types,
    status,
    max_retries,
    retry_intervals,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
