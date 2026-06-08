# GenerateODPSRequest


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**target_version** | **string** | Target ODPS version (default: 4.1) | [optional] [default to '4.1']
**output_format** | **string** | Output format: json or yaml (default: json)  * &#x60;json&#x60; - json * &#x60;yaml&#x60; - yaml | [optional] [default to OutputFormatEnum_Json]
**embed_odcs** | **boolean** | If true and contract is ODCS, embed original ODCS contract inline | [optional] [default to true]

## Example

```typescript
import { GenerateODPSRequest } from './api';

const instance: GenerateODPSRequest = {
    target_version,
    output_format,
    embed_odcs,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
