# TopologyEdge

Serializer for topology edge (relationship)

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**source** | **string** | Source domain ID | [default to undefined]
**target** | **string** | Target domain ID | [default to undefined]
**type** | **string** | Relationship type (e.g., SHARED_POLICY) | [default to undefined]
**weight** | **number** | Relationship weight/strength | [default to undefined]

## Example

```typescript
import { TopologyEdge } from './api';

const instance: TopologyEdge = {
    source,
    target,
    type,
    weight,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
