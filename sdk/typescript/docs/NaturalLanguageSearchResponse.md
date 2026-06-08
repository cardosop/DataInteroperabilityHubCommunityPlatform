# NaturalLanguageSearchResponse

Serializer for natural language search response

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**query** | **string** | Original query | [default to undefined]
**interpreted_query** | [**InterpretedQuery**](InterpretedQuery.md) | Query interpretation | [default to undefined]
**results** | **{ [key: string]: any; }** | Search results by type | [default to undefined]
**execution_time_ms** | **number** | Execution time in milliseconds | [default to undefined]
**cached** | **boolean** | Whether result was cached | [default to undefined]

## Example

```typescript
import { NaturalLanguageSearchResponse } from './api';

const instance: NaturalLanguageSearchResponse = {
    query,
    interpreted_query,
    results,
    execution_time_ms,
    cached,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
