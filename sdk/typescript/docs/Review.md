# Review

Serializer for review

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**asset_id** | **string** |  | [default to undefined]
**user_id** | **string** |  | [optional] [readonly] [default to undefined]
**review_text** | **string** |  | [default to undefined]
**rating** | **number** |  | [optional] [default to undefined]
**status** | **string** | * &#x60;PENDING&#x60; - Pending * &#x60;APPROVED&#x60; - Approved * &#x60;REJECTED&#x60; - Rejected | [optional] [readonly] [default to undefined]
**helpful_count** | **number** | Number of helpful votes | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { Review } from './api';

const instance: Review = {
    id,
    asset_id,
    user_id,
    review_text,
    rating,
    status,
    helpful_count,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
