# WranglingUndoResponse


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**session_id** | **string** |  | [default to undefined]
**undone_operation** | **{ [key: string]: any; }** |  | [default to undefined]
**can_undo** | **boolean** |  | [default to undefined]
**can_redo** | **boolean** |  | [default to undefined]
**applied_operations_count** | **number** |  | [default to undefined]

## Example

```typescript
import { WranglingUndoResponse } from './api';

const instance: WranglingUndoResponse = {
    session_id,
    undone_operation,
    can_undo,
    can_redo,
    applied_operations_count,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
