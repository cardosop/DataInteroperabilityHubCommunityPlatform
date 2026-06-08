# PipelinePreviewRequest


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**asset_id** | **string** | Source asset ID to preview | [default to undefined]
**sample_size** | **number** | Number of rows to sample (default: 100) | [optional] [default to 100]
**sampling_method** | **string** | Sampling method: first_n or random (default: first_n)  * &#x60;first_n&#x60; - first_n * &#x60;random&#x60; - random | [optional] [default to SamplingMethodEnum_FirstN]

## Example

```typescript
import { PipelinePreviewRequest } from './api';

const instance: PipelinePreviewRequest = {
    asset_id,
    sample_size,
    sampling_method,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
