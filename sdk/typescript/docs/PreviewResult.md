# PreviewResult

Serializer for PreviewResult model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** | Unique identifier for the preview result | [optional] [readonly] [default to undefined]
**preview_id** | **string** | Preview ID (hash-based identifier) | [optional] [readonly] [default to undefined]
**pipeline_id** | **string** |  | [optional] [readonly] [default to undefined]
**pipeline_name** | **string** |  | [optional] [readonly] [default to undefined]
**asset_id** | **string** |  | [optional] [readonly] [default to undefined]
**asset_name** | **string** |  | [optional] [readonly] [default to undefined]
**preview_data** | **any** | Complete preview result data (input_sample, output_sample, analysis, etc.) | [optional] [readonly] [default to undefined]
**sample_size** | **number** | Number of rows sampled | [optional] [readonly] [default to undefined]
**sampling_method** | **string** | Sampling method used (first_n, random) | [optional] [readonly] [default to undefined]
**generated_at** | **string** | When the preview was generated | [optional] [readonly] [default to undefined]
**expires_at** | **string** | When the preview expires (typically 1 hour after generation) | [optional] [readonly] [default to undefined]
**is_expired** | **boolean** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { PreviewResult } from './api';

const instance: PreviewResult = {
    id,
    preview_id,
    pipeline_id,
    pipeline_name,
    asset_id,
    asset_name,
    preview_data,
    sample_size,
    sampling_method,
    generated_at,
    expires_at,
    is_expired,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
