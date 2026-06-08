# InternalProcessExport

Request body for POST .../internal/process-export/

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**run_id** | **string** |  | [default to undefined]
**dataset_id** | **string** |  | [optional] [default to undefined]
**file_id** | **string** |  | [optional] [default to undefined]
**destination_path** | **string** |  | [optional] [default to undefined]
**destination_options** | **any** |  | [optional] [default to undefined]

## Example

```typescript
import { InternalProcessExport } from './api';

const instance: InternalProcessExport = {
    run_id,
    dataset_id,
    file_id,
    destination_path,
    destination_options,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
