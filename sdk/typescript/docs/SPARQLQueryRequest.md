# SPARQLQueryRequest


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**query** | **string** |  | [default to undefined]
**format** | **string** | Same as SPARQLQuerySerializer.format (json, csv, turtle, xml).  * &#x60;json&#x60; - json * &#x60;xml&#x60; - xml * &#x60;csv&#x60; - csv * &#x60;turtle&#x60; - turtle | [optional] [default to FormatEnum_Json]
**timeout** | **number** |  | [optional] [default to undefined]

## Example

```typescript
import { SPARQLQueryRequest } from './api';

const instance: SPARQLQueryRequest = {
    query,
    format,
    timeout,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
