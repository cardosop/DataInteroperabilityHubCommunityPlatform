# VirtualDatasetValidationResponse

Serializer for virtual dataset validation response

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**is_valid** | **boolean** | Whether validation passed | [default to undefined]
**errors** | **Array&lt;string&gt;** | List of validation errors | [default to undefined]
**warnings** | **Array&lt;string&gt;** | List of validation warnings | [default to undefined]
**details** | **{ [key: string]: any; }** | Detailed validation results | [default to undefined]

## Example

```typescript
import { VirtualDatasetValidationResponse } from './api';

const instance: VirtualDatasetValidationResponse = {
    is_valid,
    errors,
    warnings,
    details,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
