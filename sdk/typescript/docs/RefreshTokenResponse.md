# RefreshTokenResponse

Serializer for refresh token response (for listing active sessions)

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [default to undefined]
**created_at** | **string** |  | [default to undefined]
**expires_at** | **string** |  | [default to undefined]
**revoked_at** | **string** |  | [default to undefined]
**is_current** | **boolean** | Whether this is the current session\&#39;s refresh token | [default to undefined]

## Example

```typescript
import { RefreshTokenResponse } from './api';

const instance: RefreshTokenResponse = {
    id,
    created_at,
    expires_at,
    revoked_at,
    is_current,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
