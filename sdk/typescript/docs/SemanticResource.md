# SemanticResource

Serializer for SemanticResource model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this semantic resource belongs to (nullable for global classes) | [optional] [readonly] [default to undefined]
**resource_type** | **string** | Resource type: ASSET, CONTRACT, DATASET, FIELD, etc.  * &#x60;ASSET&#x60; - Asset * &#x60;CONTRACT&#x60; - Contract * &#x60;DATASET&#x60; - Dataset * &#x60;FIELD&#x60; - Field * &#x60;DQ_RUN&#x60; - DQ Run * &#x60;COMPLIANCE_RUN&#x60; - Compliance Run * &#x60;LISTING&#x60; - Listing | [default to undefined]
**resource_id** | **string** | UUID of the resource being mapped | [default to undefined]
**uri** | **string** | Stable URI for the resource (e.g., https://hub.example.com/id/asset/{uuid}) | [default to undefined]
**status** | **string** | Semantic mapping status: ACTIVE, DEGRADED, STALE  * &#x60;ACTIVE&#x60; - Active * &#x60;DEGRADED&#x60; - Degraded * &#x60;STALE&#x60; - Stale * &#x60;MINTED&#x60; - Minted * &#x60;PUBLISHED&#x60; - Published * &#x60;UPDATED&#x60; - Updated * &#x60;TOMBSTONED&#x60; - Tombstoned | [optional] [default to undefined]
**last_mapped_at** | **string** | When the resource was last mapped to RDF | [optional] [readonly] [default to undefined]
**mapping_version** | **string** | Semantic mapping version used | [optional] [default to undefined]
**metadata_json** | **any** | Additional metadata (links, relationships, etc.) | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]
**canonical_iri** | **string** | Canonical Linked Data IRI: {SEMANTIC_BASE_IRI}/id/semantic_resource/{id}. Stable identifier for JSON-LD dereference. See Phase 226 G7a. | [optional] [readonly] [default to undefined]

## Example

```typescript
import { SemanticResource } from './api';

const instance: SemanticResource = {
    id,
    tenant,
    resource_type,
    resource_id,
    uri,
    status,
    last_mapped_at,
    mapping_version,
    metadata_json,
    created_at,
    updated_at,
    canonical_iri,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
