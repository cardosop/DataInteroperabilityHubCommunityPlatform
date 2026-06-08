# PolicyApplication

Serializer for PolicyApplication model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**domain_id** | **string** |  | [optional] [readonly] [default to undefined]
**domain_name** | **string** |  | [optional] [readonly] [default to undefined]
**policy_id** | **string** |  | [optional] [readonly] [default to undefined]
**policy_name** | **string** |  | [optional] [readonly] [default to undefined]
**applied_by_id** | **string** |  | [optional] [readonly] [default to undefined]
**applied_by_email** | **string** |  | [optional] [readonly] [default to undefined]
**overrides** | **any** | Policy overrides as JSON (conditions, effect, priority, etc.) | [optional] [default to undefined]
**status** | **string** | * &#x60;PENDING&#x60; - Pending * &#x60;APPLIED&#x60; - Applied * &#x60;FAILED&#x60; - Failed * &#x60;REVOKED&#x60; - Revoked | [default to undefined]
**applied_at** | **string** | Timestamp when policy was applied | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { PolicyApplication } from './api';

const instance: PolicyApplication = {
    id,
    domain_id,
    domain_name,
    policy_id,
    policy_name,
    applied_by_id,
    applied_by_email,
    overrides,
    status,
    applied_at,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
