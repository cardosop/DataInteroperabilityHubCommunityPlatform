# VirtualizationTopologyEdge

Serializer for topology edge (relationship)

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**source** | **string** | Source dataset ID | [default to undefined]
**target** | **string** | Target dataset ID | [default to undefined]
**type** | **string** | Relationship type (e.g., SHARED_SOURCE) | [default to undefined]
**weight** | **number** | Relationship weight/strength | [default to undefined]
**shared_sources** | **Array&lt;string&gt;** | List of shared source identifiers | [optional] [default to undefined]

## Example

```typescript
import { VirtualizationTopologyEdge } from './api';

const instance: VirtualizationTopologyEdge = {
    source,
    target,
    type,
    weight,
    shared_sources,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
