# FieldMatch

Serializer for field match

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**source_field** | **string** | Source field name | [default to undefined]
**target_field** | **string** | Target field name | [default to undefined]
**confidence** | **number** | Match confidence (0-1) | [default to undefined]
**match_type** | **string** | Match type (exact, fuzzy, semantic) | [default to undefined]

## Example

```typescript
import { FieldMatch } from './api';

const instance: FieldMatch = {
    source_field,
    target_field,
    confidence,
    match_type,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
