# PasswordResetConfirm

Serializer for password reset confirmation (11.3: token is plaintext UUID string)

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**token** | **string** |  | [default to undefined]
**new_password** | **string** |  | [default to undefined]

## Example

```typescript
import { PasswordResetConfirm } from './api';

const instance: PasswordResetConfirm = {
    token,
    new_password,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
