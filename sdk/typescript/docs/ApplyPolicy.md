# ApplyPolicy

Serializer for applying a policy to a domain

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**policy_id** | **string** | Policy ID to apply to the domain | [default to undefined]
**overrides** | **{ [key: string]: any; }** | Policy overrides as JSON (conditions, effect, priority, etc.) | [optional] [default to undefined]

## Example

```typescript
import { ApplyPolicy } from './api';

const instance: ApplyPolicy = {
    policy_id,
    overrides,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
