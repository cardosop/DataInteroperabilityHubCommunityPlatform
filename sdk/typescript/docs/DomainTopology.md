# DomainTopology

Serializer for single domain topology view

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**domain** | [**TopologyNode**](TopologyNode.md) | Domain node | [default to undefined]
**relationships** | [**Array&lt;TopologyEdge&gt;**](TopologyEdge.md) | Relationships for this domain | [default to undefined]
**health_metrics** | [**HealthMetrics**](HealthMetrics.md) | Domain health metrics | [default to undefined]

## Example

```typescript
import { DomainTopology } from './api';

const instance: DomainTopology = {
    domain,
    relationships,
    health_metrics,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
