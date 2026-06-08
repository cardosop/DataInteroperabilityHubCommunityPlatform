# PatchedTenantSparqlEndpoint

Serializer for ``TenantSparqlEndpoint`` rows (Phase 230.8 / REQ-SEM-FED-001).  The CRUD viewset is mounted at ``/api/v1/tenants/<id>/sparql-endpoints/``. SSRF + scheme validation lives in the view (so the rejection response can carry a stable machine-readable ``code``); the serializer focuses on shape + uniqueness.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**name** | **string** | Human-readable label for the endpoint (e.g. \&#39;partner-X\&#39;). | [optional] [default to undefined]
**endpoint_url** | **string** | Canonical SPARQL endpoint URL.  Compared against SERVICE clauses in incoming queries by exact-match (after scheme + host + path normalisation). | [optional] [default to undefined]
**is_active** | **boolean** | Inactive entries are NOT treated as allowlisted.  Toggle False to revoke without deleting the audit trail. | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { PatchedTenantSparqlEndpoint } from './api';

const instance: PatchedTenantSparqlEndpoint = {
    id,
    name,
    endpoint_url,
    is_active,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
