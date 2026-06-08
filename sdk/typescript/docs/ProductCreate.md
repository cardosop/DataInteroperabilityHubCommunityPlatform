# ProductCreate

Serializer for Product-First creation (ODPS)

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**original_raw** | **string** | ODPS document content (JSON or YAML). Max 2 MB. | [default to undefined]
**original_format** | **string** | ODPS document format: JSON or YAML  * &#x60;JSON&#x60; - JSON * &#x60;YAML&#x60; - YAML | [default to undefined]
**resolve_external_refs** | **boolean** | If True, external $ref references will be resolved. If False, external refs will be disabled (raises error if found). | [optional] [default to true]
**asset_id** | **string** | Optional asset ID to link contracts to | [optional] [default to undefined]

## Example

```typescript
import { ProductCreate } from './api';

const instance: ProductCreate = {
    original_raw,
    original_format,
    resolve_external_refs,
    asset_id,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
