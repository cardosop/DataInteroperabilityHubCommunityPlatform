# ABTest

Serializer for A/B test response

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**ab_test_id** | **string** |  | [optional] [readonly] [default to undefined]
**model_id** | **string** |  | [default to undefined]
**variant_id** | **string** |  | [default to undefined]
**traffic_split** | **string** |  | [default to undefined]
**status** | **string** |  | [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { ABTest } from './api';

const instance: ABTest = {
    id,
    ab_test_id,
    model_id,
    variant_id,
    traffic_split,
    status,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
