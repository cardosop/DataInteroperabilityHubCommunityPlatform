# SchemaMatchingResponse

Serializer for schema matching response

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**matches** | [**Array&lt;FieldMatch&gt;**](FieldMatch.md) | Field matches | [default to undefined]
**confidence** | **number** | Overall confidence (0-1) | [default to undefined]
**suggestions** | **Array&lt;string&gt;** | Suggestions for improvement | [default to undefined]
**execution_time_ms** | **number** | Execution time in milliseconds | [default to undefined]

## Example

```typescript
import { SchemaMatchingResponse } from './api';

const instance: SchemaMatchingResponse = {
    matches,
    confidence,
    suggestions,
    execution_time_ms,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
