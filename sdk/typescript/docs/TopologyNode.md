# TopologyNode

Serializer for topology node (domain)

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** | Domain ID | [default to undefined]
**name** | **string** | Domain name | [default to undefined]
**description** | **string** | Domain description | [optional] [default to undefined]
**status** | **string** | Domain status | [default to undefined]
**owner_id** | **string** | Owner user ID | [optional] [default to undefined]
**created_at** | **string** | Domain creation timestamp | [optional] [default to undefined]
**health_metrics** | [**HealthMetrics**](HealthMetrics.md) | Health metrics (if include_health_metrics&#x3D;true) | [optional] [default to undefined]

## Example

```typescript
import { TopologyNode } from './api';

const instance: TopologyNode = {
    id,
    name,
    description,
    status,
    owner_id,
    created_at,
    health_metrics,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
