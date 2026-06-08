# WranglingResult

Serializer for wrangling operation result response

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**session_id** | **string** |  | [default to undefined]
**operation_id** | **string** |  | [default to undefined]
**result** | **{ [key: string]: any; }** | Operation result (sample_data, row counts, columns) | [default to undefined]
**can_undo** | **boolean** |  | [default to undefined]
**can_redo** | **boolean** |  | [default to undefined]
**applied_operations_count** | **number** |  | [default to undefined]
**wrangling_script** | **string** |  | [default to undefined]

## Example

```typescript
import { WranglingResult } from './api';

const instance: WranglingResult = {
    session_id,
    operation_id,
    result,
    can_undo,
    can_redo,
    applied_operations_count,
    wrangling_script,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
