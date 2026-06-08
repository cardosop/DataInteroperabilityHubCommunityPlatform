# PatchedInternalUpdateRun

Request body for PATCH .../internal/runs/{run_id}/

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**status** | **string** | * &#x60;RUNNING&#x60; - RUNNING * &#x60;COMPLETED&#x60; - COMPLETED * &#x60;FAILED&#x60; - FAILED * &#x60;CANCELLED&#x60; - CANCELLED | [optional] [default to undefined]
**items_found** | **number** |  | [optional] [default to undefined]
**items_exported** | **number** |  | [optional] [default to undefined]
**items_failed** | **number** |  | [optional] [default to undefined]
**result_json** | **any** |  | [optional] [default to undefined]
**completed_at** | **string** |  | [optional] [default to undefined]
**prefect_flow_run_id** | **string** |  | [optional] [default to undefined]

## Example

```typescript
import { PatchedInternalUpdateRun } from './api';

const instance: PatchedInternalUpdateRun = {
    status,
    items_found,
    items_exported,
    items_failed,
    result_json,
    completed_at,
    prefect_flow_run_id,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
