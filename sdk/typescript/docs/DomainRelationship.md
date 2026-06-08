# DomainRelationship

Serializer for domain relationships response

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**relationships** | [**Array&lt;TopologyEdge&gt;**](TopologyEdge.md) | List of domain relationships | [default to undefined]
**total_count** | **number** | Total number of relationships | [default to undefined]
**relationship_types** | **{ [key: string]: any; }** | Count of relationships by type | [default to undefined]

## Example

```typescript
import { DomainRelationship } from './api';

const instance: DomainRelationship = {
    relationships,
    total_count,
    relationship_types,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
