# VirtualizationTopologyMetadata

Serializer for topology metadata

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**tenant_id** | **string** | Tenant ID | [default to undefined]
**dataset_count** | **number** | Number of datasets | [default to undefined]
**relationship_count** | **number** | Number of relationships | [default to undefined]
**generated_at** | **string** | Topology generation timestamp | [default to undefined]

## Example

```typescript
import { VirtualizationTopologyMetadata } from './api';

const instance: VirtualizationTopologyMetadata = {
    tenant_id,
    dataset_count,
    relationship_count,
    generated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
