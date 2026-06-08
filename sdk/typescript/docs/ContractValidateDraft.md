# ContractValidateDraft

Serializer for dry-run contract validation (Phase 219.4).  Accepts raw contract content for normalization without persisting.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**original_raw** | **string** | Raw contract content (JSON or YAML) to validate. Max 2 MB. | [default to undefined]
**original_format** | **string** | Content format: JSON or YAML  * &#x60;JSON&#x60; - JSON * &#x60;YAML&#x60; - YAML | [default to undefined]

## Example

```typescript
import { ContractValidateDraft } from './api';

const instance: ContractValidateDraft = {
    original_raw,
    original_format,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
