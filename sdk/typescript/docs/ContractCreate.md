# ContractCreate

Serializer for contract creation

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**asset_id** | **string** |  | [optional] [default to undefined]
**original_raw** | **string** | Original contract content (JSON or YAML). Max 2 MB. | [default to undefined]
**original_format** | **string** | * &#x60;JSON&#x60; - JSON * &#x60;YAML&#x60; - YAML | [default to undefined]
**original_spec_type** | **string** | Optional: will be auto-detected if not provided  * &#x60;ODCS&#x60; - ODCS * &#x60;ODPS&#x60; - ODPS | [optional] [default to undefined]
**disable_external_refs** | **boolean** | If True, external $ref references will be disabled (raises error if found). If False, external refs will be resolved normally. | [optional] [default to false]
**remove_external_refs** | **boolean** | If True, external $ref references will be removed from the document. If False, external refs will be resolved and replaced with their content. | [optional] [default to false]

## Example

```typescript
import { ContractCreate } from './api';

const instance: ContractCreate = {
    asset_id,
    original_raw,
    original_format,
    original_spec_type,
    disable_external_refs,
    remove_external_refs,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
