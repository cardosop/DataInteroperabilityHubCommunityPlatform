# Refund

Serializer for marketplace order refund (provider or platform admin).

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**reason** | **string** | Human-readable reason for the refund | [default to undefined]
**amount** | **string** | Amount to refund; omit for full remaining balance | [optional] [default to undefined]

## Example

```typescript
import { Refund } from './api';

const instance: Refund = {
    reason,
    amount,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
