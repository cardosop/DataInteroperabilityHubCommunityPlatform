# InternalCreateRun

Request body for POST .../internal/runs/

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**scheduled_export_id** | **string** |  | [default to undefined]
**prefect_flow_run_id** | **string** |  | [optional] [default to undefined]
**idempotency_key** | **string** |  | [optional] [default to undefined]

## Example

```typescript
import { InternalCreateRun } from './api';

const instance: InternalCreateRun = {
    scheduled_export_id,
    prefect_flow_run_id,
    idempotency_key,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
