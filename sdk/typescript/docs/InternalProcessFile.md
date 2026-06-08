# InternalProcessFile

Request for POST .../internal/process-file/ (multipart or JSON with base64 file_content).

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**run_id** | **string** |  | [default to undefined]
**file_path** | **string** |  | [default to undefined]
**asset_id** | **string** |  | [optional] [default to undefined]
**contract_id** | **string** |  | [optional] [default to undefined]
**dq_options** | **any** |  | [optional] [default to undefined]
**file_content** | **string** |  | [optional] [default to undefined]

## Example

```typescript
import { InternalProcessFile } from './api';

const instance: InternalProcessFile = {
    run_id,
    file_path,
    asset_id,
    contract_id,
    dq_options,
    file_content,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
