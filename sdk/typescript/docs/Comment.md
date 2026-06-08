# Comment

Serializer for comment

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**asset_id** | **string** |  | [default to undefined]
**user_id** | **string** |  | [optional] [readonly] [default to undefined]
**parent_comment_id** | **string** |  | [optional] [default to undefined]
**comment_text** | **string** |  | [default to undefined]
**status** | **string** | * &#x60;PENDING&#x60; - Pending * &#x60;APPROVED&#x60; - Approved * &#x60;REJECTED&#x60; - Rejected | [optional] [readonly] [default to undefined]
**mentions** | **any** | List of mentioned user IDs | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { Comment } from './api';

const instance: Comment = {
    id,
    asset_id,
    user_id,
    parent_comment_id,
    comment_text,
    status,
    mentions,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
