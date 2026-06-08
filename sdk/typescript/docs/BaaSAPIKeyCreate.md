# BaaSAPIKeyCreate

Serializer for creating BaaS API keys

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**name** | **string** | Human-readable name for the API key | [default to undefined]
**tier** | **string** | API tier (FREE, PRO, ENTERPRISE)  * &#x60;FREE&#x60; - Free * &#x60;PRO&#x60; - Pro * &#x60;ENTERPRISE&#x60; - Enterprise | [optional] [default to TierEnum_Free]
**expires_at** | **string** | Optional expiration timestamp (ISO format) | [optional] [default to undefined]
**customer_id** | **string** |  | [optional] [default to '']
**customer_name** | **string** |  | [optional] [default to '']
**customer_email** | **string** |  | [optional] [default to '']
**customer_metadata** | **any** |  | [optional] [default to undefined]
**pricing** | **any** | Optional pricing config for this key | [optional] [default to undefined]

## Example

```typescript
import { BaaSAPIKeyCreate } from './api';

const instance: BaaSAPIKeyCreate = {
    name,
    tier,
    expires_at,
    customer_id,
    customer_name,
    customer_email,
    customer_metadata,
    pricing,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
