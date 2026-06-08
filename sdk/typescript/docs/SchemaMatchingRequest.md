# SchemaMatchingRequest

Serializer for schema matching request

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**source_schema** | **{ [key: string]: any; }** | Source schema definition | [default to undefined]
**target_schema** | **{ [key: string]: any; }** | Target schema definition | [default to undefined]
**context** | **{ [key: string]: any; }** | Optional context for matching | [optional] [default to undefined]

## Example

```typescript
import { SchemaMatchingRequest } from './api';

const instance: SchemaMatchingRequest = {
    source_schema,
    target_schema,
    context,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
