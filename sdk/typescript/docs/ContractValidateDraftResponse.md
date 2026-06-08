# ContractValidateDraftResponse

Response serializer for validate-draft endpoint (OpenAPI docs only).

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**valid** | **boolean** |  | [default to undefined]
**detected_spec_type** | **string** |  | [default to undefined]
**detected_spec_version** | **string** |  | [default to undefined]
**normalization_status** | **string** |  | [default to undefined]
**normalization_errors** | **Array&lt;string&gt;** |  | [default to undefined]
**normalization_warnings** | **Array&lt;string&gt;** |  | [default to undefined]

## Example

```typescript
import { ContractValidateDraftResponse } from './api';

const instance: ContractValidateDraftResponse = {
    valid,
    detected_spec_type,
    detected_spec_version,
    normalization_status,
    normalization_errors,
    normalization_warnings,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
