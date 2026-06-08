# PipelineExecutionResult

Serializer for execution result response

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**execution_id** | **string** |  | [default to undefined]
**status** | **string** |  | [default to undefined]
**result_asset_id** | **string** |  | [default to undefined]
**result_asset_name** | **string** |  | [default to undefined]
**metrics** | **{ [key: string]: any; }** |  | [default to undefined]
**execution_log** | **Array&lt;{ [key: string]: any; }&gt;** |  | [default to undefined]
**started_at** | **string** |  | [default to undefined]
**completed_at** | **string** |  | [default to undefined]
**duration_seconds** | **number** |  | [default to undefined]
**error_message** | **string** |  | [default to undefined]

## Example

```typescript
import { PipelineExecutionResult } from './api';

const instance: PipelineExecutionResult = {
    execution_id,
    status,
    result_asset_id,
    result_asset_name,
    metrics,
    execution_log,
    started_at,
    completed_at,
    duration_seconds,
    error_message,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
