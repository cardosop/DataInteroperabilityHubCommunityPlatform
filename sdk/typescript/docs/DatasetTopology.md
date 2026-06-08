# DatasetTopology

Serializer for single dataset topology view

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**dataset** | [**VirtualizationTopologyNode**](VirtualizationTopologyNode.md) | Dataset node | [default to undefined]
**relationships** | [**Array&lt;VirtualizationTopologyEdge&gt;**](VirtualizationTopologyEdge.md) | Relationships for this dataset | [default to undefined]
**health_metrics** | [**VirtualizationHealthMetrics**](VirtualizationHealthMetrics.md) | Dataset health metrics | [default to undefined]

## Example

```typescript
import { DatasetTopology } from './api';

const instance: DatasetTopology = {
    dataset,
    relationships,
    health_metrics,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
