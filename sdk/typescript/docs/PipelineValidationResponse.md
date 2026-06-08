# PipelineValidationResponse

Serializer for pipeline validation response

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**is_valid** | **boolean** |  | [default to undefined]
**errors** | **Array&lt;string&gt;** |  | [default to undefined]
**warnings** | **Array&lt;string&gt;** |  | [default to undefined]
**details** | **{ [key: string]: any; }** |  | [default to undefined]

## Example

```typescript
import { PipelineValidationResponse } from './api';

const instance: PipelineValidationResponse = {
    is_valid,
    errors,
    warnings,
    details,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
