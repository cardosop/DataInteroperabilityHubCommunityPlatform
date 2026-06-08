# APIInfo

Serializer for API info endpoint

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**name** | **string** |  | [default to undefined]
**version** | **string** |  | [default to undefined]
**base_url** | **string** |  | [default to undefined]
**documentation** | **{ [key: string]: any; }** |  | [default to undefined]
**endpoints** | **{ [key: string]: any; }** |  | [default to undefined]

## Example

```typescript
import { APIInfo } from './api';

const instance: APIInfo = {
    name,
    version,
    base_url,
    documentation,
    endpoints,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
