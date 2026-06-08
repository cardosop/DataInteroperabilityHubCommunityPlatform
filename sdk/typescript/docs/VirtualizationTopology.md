# VirtualizationTopology

Serializer for full virtualization topology response

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**nodes** | [**Array&lt;VirtualizationTopologyNode&gt;**](VirtualizationTopologyNode.md) | List of dataset nodes | [default to undefined]
**edges** | [**Array&lt;VirtualizationTopologyEdge&gt;**](VirtualizationTopologyEdge.md) | List of dataset relationships | [default to undefined]
**metadata** | [**VirtualizationTopologyMetadata**](VirtualizationTopologyMetadata.md) | Topology metadata | [default to undefined]
**summary** | [**VirtualizationTopologySummary**](VirtualizationTopologySummary.md) | Summary statistics | [default to undefined]

## Example

```typescript
import { VirtualizationTopology } from './api';

const instance: VirtualizationTopology = {
    nodes,
    edges,
    metadata,
    summary,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
