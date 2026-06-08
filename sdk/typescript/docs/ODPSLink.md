# ODPSLink

Serializer for ODPS linking request

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**odps_contract_id** | **string** | Existing ODPS contract ID to link (mutually exclusive with original_raw) | [optional] [default to undefined]
**original_raw** | **string** | ODPS document content (JSON or YAML) - mutually exclusive with odps_contract_id. Max 2 MB. | [optional] [default to undefined]
**original_format** | **string** | ODPS document format: JSON or YAML (required if original_raw is provided)  * &#x60;JSON&#x60; - JSON * &#x60;YAML&#x60; - YAML | [optional] [default to undefined]
**resolve_external_refs** | **boolean** | If True, external $ref references will be resolved. If False, external refs will be disabled (raises error if found). Only used if original_raw is provided. | [optional] [default to true]

## Example

```typescript
import { ODPSLink } from './api';

const instance: ODPSLink = {
    odps_contract_id,
    original_raw,
    original_format,
    resolve_external_refs,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
