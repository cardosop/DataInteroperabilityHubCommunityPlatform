# NaturalLanguageSearchRequest

Serializer for natural language search request

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**query** | **string** | Natural language search query | [default to undefined]
**result_types** | **Array&lt;string&gt;** | Types of results to return | [optional] [default to undefined]
**filters** | **{ [key: string]: any; }** | Additional filters to apply | [optional] [default to undefined]

## Example

```typescript
import { NaturalLanguageSearchRequest } from './api';

const instance: NaturalLanguageSearchRequest = {
    query,
    result_types,
    filters,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
