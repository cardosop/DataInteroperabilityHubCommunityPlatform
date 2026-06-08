# WranglingSession

Serializer for WranglingSession model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** | Unique identifier for the wrangling session | [optional] [readonly] [default to undefined]
**name** | **string** | Session name | [default to undefined]
**description** | **string** | Session description | [optional] [default to undefined]
**asset_id** | **string** |  | [optional] [readonly] [default to undefined]
**asset_name** | **string** |  | [optional] [readonly] [default to undefined]
**current_state** | **any** | Current state snapshot after all operations | [optional] [readonly] [default to undefined]
**operation_history** | **any** | List of operations performed in this session | [optional] [readonly] [default to undefined]
**history_position** | **number** | Current position in operation history (-1 &#x3D; at end) | [optional] [readonly] [default to undefined]
**wrangling_script** | **string** | Generated script representation of operations | [optional] [readonly] [default to undefined]
**metadata** | **any** | Additional metadata | [optional] [readonly] [default to undefined]
**can_undo** | **boolean** |  | [optional] [readonly] [default to undefined]
**can_redo** | **boolean** |  | [optional] [readonly] [default to undefined]
**applied_operations_count** | **number** |  | [optional] [readonly] [default to undefined]
**created_at** | **string** | When the session was created | [optional] [readonly] [default to undefined]
**updated_at** | **string** | When the session was last updated | [optional] [readonly] [default to undefined]

## Example

```typescript
import { WranglingSession } from './api';

const instance: WranglingSession = {
    id,
    name,
    description,
    asset_id,
    asset_name,
    current_state,
    operation_history,
    history_position,
    wrangling_script,
    metadata,
    can_undo,
    can_redo,
    applied_operations_count,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
