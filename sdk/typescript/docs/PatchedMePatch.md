# PatchedMePatch

Serializer for PATCH /auth/me/ — partial profile update

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**display_name** | **string** | User display name | [optional] [default to undefined]
**avatar** | **string** | URL to user avatar image | [optional] [default to undefined]
**preferences** | **any** | User preferences (theme, language, notifications, etc.) | [optional] [default to undefined]

## Example

```typescript
import { PatchedMePatch } from './api';

const instance: PatchedMePatch = {
    display_name,
    avatar,
    preferences,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
