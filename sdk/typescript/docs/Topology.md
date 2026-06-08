# Topology

Serializer for full mesh topology response

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**nodes** | [**Array&lt;TopologyNode&gt;**](TopologyNode.md) | List of domain nodes | [default to undefined]
**edges** | [**Array&lt;TopologyEdge&gt;**](TopologyEdge.md) | List of domain relationships | [default to undefined]
**metadata** | [**TopologyMetadata**](TopologyMetadata.md) | Topology metadata | [default to undefined]
**summary** | [**TopologySummary**](TopologySummary.md) | Summary statistics | [default to undefined]

## Example

```typescript
import { Topology } from './api';

const instance: Topology = {
    nodes,
    edges,
    metadata,
    summary,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
