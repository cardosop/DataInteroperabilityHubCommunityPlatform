# LineageSubscription

REQ-LIN-F3-002 / F3-003 read+create shape.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**user** | **string** |  | [optional] [readonly] [default to undefined]
**source_contract** | **string** |  | [optional] [default to undefined]
**source_asset** | **string** |  | [optional] [default to undefined]
**severity_threshold** | **string** | * &#x60;LOW&#x60; - Low * &#x60;MEDIUM&#x60; - Medium * &#x60;HIGH&#x60; - High * &#x60;CRITICAL&#x60; - Critical | [optional] [default to undefined]
**in_app** | **boolean** |  | [optional] [default to undefined]
**email** | **boolean** |  | [optional] [default to undefined]
**slack** | **boolean** |  | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**last_dispatched_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { LineageSubscription } from './api';

const instance: LineageSubscription = {
    id,
    user,
    source_contract,
    source_asset,
    severity_threshold,
    in_app,
    email,
    slack,
    created_at,
    last_dispatched_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
