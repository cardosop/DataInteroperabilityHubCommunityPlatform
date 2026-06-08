# InterpretedQuery

Serializer for interpreted query

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**intent** | **string** | Query intent | [default to undefined]
**entities** | **Array&lt;string&gt;** | Extracted entities | [default to undefined]
**time_range** | **string** | Time range if mentioned | [optional] [default to undefined]
**structured_query** | [**StructuredQuery**](StructuredQuery.md) | Structured query | [default to undefined]

## Example

```typescript
import { InterpretedQuery } from './api';

const instance: InterpretedQuery = {
    intent,
    entities,
    time_range,
    structured_query,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
