# TopologyMetadata

Serializer for topology metadata

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**tenant_id** | **string** | Tenant ID | [default to undefined]
**domain_count** | **number** | Number of domains | [default to undefined]
**relationship_count** | **number** | Number of relationships | [default to undefined]
**generated_at** | **string** | Topology generation timestamp | [default to undefined]

## Example

```typescript
import { TopologyMetadata } from './api';

const instance: TopologyMetadata = {
    tenant_id,
    domain_count,
    relationship_count,
    generated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
