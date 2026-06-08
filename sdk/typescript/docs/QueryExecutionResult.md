# QueryExecutionResult

Serializer for query execution result

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**execution_id** | **string** | Query execution ID | [default to undefined]
**data** | **any** | Result data (list of rows or formatted string) | [default to undefined]
**total_count** | **number** | Total number of rows | [default to undefined]
**returned_count** | **number** | Number of rows returned in this response | [default to undefined]
**format** | **string** | Output format (json, csv, parquet) | [default to undefined]
**content_type** | **string** | Content type for the response | [default to undefined]
**pagination** | **{ [key: string]: any; }** | Pagination metadata (if applicable) | [optional] [default to undefined]
**stream_enabled** | **boolean** | Whether streaming is enabled | [default to undefined]
**stream_url** | **string** | Streaming URL (if stream_enabled&#x3D;True) | [optional] [default to undefined]

## Example

```typescript
import { QueryExecutionResult } from './api';

const instance: QueryExecutionResult = {
    execution_id,
    data,
    total_count,
    returned_count,
    format,
    content_type,
    pagination,
    stream_enabled,
    stream_url,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
