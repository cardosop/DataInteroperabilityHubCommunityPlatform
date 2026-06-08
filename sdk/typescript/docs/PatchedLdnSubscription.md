# PatchedLdnSubscription


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**target_inbox_url** | **string** | Absolute URL of the partner\&#39;s inbox. MUST be HTTPS in production; tested explicitly at signal-handler time. | [optional] [default to undefined]
**resource_type_filter** | **string** | Restrict deliveries to a single resource type (asset / contract / dataset). Empty &#x3D; deliver all. | [optional] [default to undefined]
**is_active** | **boolean** |  | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { PatchedLdnSubscription } from './api';

const instance: PatchedLdnSubscription = {
    id,
    target_inbox_url,
    resource_type_filter,
    is_active,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
