# PatchedAsset

Serializer for Asset model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this asset belongs to | [optional] [readonly] [default to undefined]
**key** | **string** | Human-friendly identifier, unique per tenant | [optional] [default to undefined]
**name** | **string** | Asset name | [optional] [default to undefined]
**description** | **string** | Asset description | [optional] [default to undefined]
**domain** | **string** | Domain (e.g., marketing, finance) | [optional] [default to undefined]
**status** | **string** | Asset lifecycle status: DRAFT, ACTIVE, PUBLIC, RETIRED  * &#x60;DRAFT&#x60; - Draft * &#x60;ACTIVE&#x60; - Active * &#x60;PUBLIC&#x60; - Public * &#x60;RETIRED&#x60; - Retired | [optional] [default to undefined]
**visibility** | **string** | DERIVED visibility (Phase 250.3.B / D250.4): PUBLIC iff status&#x3D;&#x3D;PUBLIC, else INTERNAL. The legacy stored column is being removed in phase-2 — clients SHOULD read this field but treat it as read-only. | [optional] [readonly] [default to undefined]
**dq_status** | **string** | Data Quality status: UNKNOWN, PASS, WARN, FAIL  * &#x60;UNKNOWN&#x60; - Unknown * &#x60;PASS&#x60; - Pass * &#x60;WARN&#x60; - Warning * &#x60;FAIL&#x60; - Fail | [optional] [readonly] [default to undefined]
**compliance_status** | **string** | Compliance status: UNKNOWN, PASS, WARN, FAIL  * &#x60;UNKNOWN&#x60; - Unknown * &#x60;PASS&#x60; - Pass * &#x60;WARN&#x60; - Warning * &#x60;FAIL&#x60; - Fail | [optional] [readonly] [default to undefined]
**semantic_status** | **string** | Phase 250.7.A — semantic-mapping + search-indexing status: UNKNOWN (default; not yet checked), PASS (both succeeded), WARN (partial degradation reserved for future granular failures), FAIL (one or both failed; asset is ACTIVE but not discoverable in semantic search).  * &#x60;UNKNOWN&#x60; - Unknown * &#x60;PASS&#x60; - Pass * &#x60;WARN&#x60; - Warning * &#x60;FAIL&#x60; - Fail | [optional] [readonly] [default to undefined]
**version** | **number** | Optimistic locking version counter | [optional] [readonly] [default to undefined]
**created_by** | **string** | User who created the asset | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]
**contract_id** | **string** |  | [optional] [readonly] [default to undefined]
**dataset_id** | **string** |  | [optional] [readonly] [default to undefined]
**canonical_iri** | **string** | Canonical Linked Data IRI: {SEMANTIC_BASE_IRI}/id/asset/{id}. Stable identifier for JSON-LD dereference, SPARQL queries, and cross-system references. See Phase 226 G7a. | [optional] [readonly] [default to undefined]
**latest_compliance_run** | **string** | Latest SUCCEEDED compliance run for this asset (Phase 231.3). Omitted when no successful run exists. | [optional] [readonly] [default to undefined]

## Example

```typescript
import { PatchedAsset } from './api';

const instance: PatchedAsset = {
    id,
    tenant,
    key,
    name,
    description,
    domain,
    status,
    visibility,
    dq_status,
    compliance_status,
    semantic_status,
    version,
    created_by,
    created_at,
    updated_at,
    contract_id,
    dataset_id,
    canonical_iri,
    latest_compliance_run,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
