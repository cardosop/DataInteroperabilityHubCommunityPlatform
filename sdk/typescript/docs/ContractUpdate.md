# ContractUpdate

Serializer for contract update

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**original_raw** | **string** | Updated contract content (JSON or YAML). Max 2 MB. | [optional] [default to undefined]
**original_format** | **string** | * &#x60;JSON&#x60; - JSON * &#x60;YAML&#x60; - YAML | [optional] [default to undefined]
**original_spec_type** | **string** | Spec type (ODCS/ODPS) for the new content; used when updating original_raw.  * &#x60;ODCS&#x60; - ODCS * &#x60;ODPS&#x60; - ODPS | [optional] [default to undefined]
**original_spec_version** | **string** | Spec version (e.g. 3.0.2, 4.1); used with original_spec_type when updating. | [optional] [default to undefined]
**status** | **string** | * &#x60;DRAFT&#x60; - Draft * &#x60;ACTIVE&#x60; - Active * &#x60;RETIRED&#x60; - Retired | [optional] [default to undefined]
**remove_external_refs** | **boolean** | If True, external $ref references will be removed from the document. If False, external refs will be resolved and replaced with their content. | [optional] [default to false]

## Example

```typescript
import { ContractUpdate } from './api';

const instance: ContractUpdate = {
    original_raw,
    original_format,
    original_spec_type,
    original_spec_version,
    status,
    remove_external_refs,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
