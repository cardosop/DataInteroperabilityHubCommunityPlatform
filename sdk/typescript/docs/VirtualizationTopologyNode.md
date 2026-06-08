# VirtualizationTopologyNode

Serializer for topology node (virtual dataset)

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** | Virtual dataset ID | [default to undefined]
**name** | **string** | Dataset name | [default to undefined]
**description** | **string** | Dataset description | [default to undefined]
**status** | **string** | Dataset status | [default to undefined]
**query_type** | **string** | Query type | [default to undefined]
**version** | **string** | Dataset version | [default to undefined]
**created_by_id** | **string** | User ID who created the dataset | [default to undefined]
**created_at** | **string** | Dataset creation timestamp | [default to undefined]
**updated_at** | **string** | Dataset last update timestamp | [default to undefined]
**health_metrics** | [**VirtualizationHealthMetrics**](VirtualizationHealthMetrics.md) | Health metrics (if include_health_metrics&#x3D;true) | [optional] [default to undefined]

## Example

```typescript
import { VirtualizationTopologyNode } from './api';

const instance: VirtualizationTopologyNode = {
    id,
    name,
    description,
    status,
    query_type,
    version,
    created_by_id,
    created_at,
    updated_at,
    health_metrics,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
