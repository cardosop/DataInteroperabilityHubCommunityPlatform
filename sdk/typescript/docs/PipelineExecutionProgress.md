# PipelineExecutionProgress

Serializer for execution progress response

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**execution_id** | **string** |  | [default to undefined]
**status** | **string** |  | [default to undefined]
**progress_percentage** | **number** |  | [default to undefined]
**current_step** | **string** |  | [default to undefined]
**total_steps** | **number** |  | [default to undefined]
**started_at** | **string** |  | [default to undefined]
**estimated_completion_at** | **string** |  | [default to undefined]
**duration_seconds** | **number** |  | [default to undefined]
**metrics** | **{ [key: string]: any; }** |  | [default to undefined]
**recent_logs** | **Array&lt;{ [key: string]: any; }&gt;** |  | [default to undefined]

## Example

```typescript
import { PipelineExecutionProgress } from './api';

const instance: PipelineExecutionProgress = {
    execution_id,
    status,
    progress_percentage,
    current_step,
    total_steps,
    started_at,
    estimated_completion_at,
    duration_seconds,
    metrics,
    recent_logs,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
