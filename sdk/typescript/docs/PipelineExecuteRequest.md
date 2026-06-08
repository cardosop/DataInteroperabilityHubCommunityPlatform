# PipelineExecuteRequest


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**asset_id** | **string** | Source asset ID to transform | [default to undefined]
**execution_mode** | **string** | Execution mode: SYNC (synchronous) or ASYNC (asynchronous)  * &#x60;SYNC&#x60; - SYNC * &#x60;ASYNC&#x60; - ASYNC | [optional] [default to undefined]

## Example

```typescript
import { PipelineExecuteRequest } from './api';

const instance: PipelineExecuteRequest = {
    asset_id,
    execution_mode,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
