# PatchedDataset

Serializer for Dataset model. UUID FKs are serialized as strings for JSON consistency.  Writable fields on update: asset, format (others are read-only). name: Read-only, computed from instance.file.name (not persisted). description: Not supported; Dataset model has no description field (not persisted).

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this dataset belongs to | [optional] [readonly] [default to undefined]
**asset** | **string** | Asset this dataset belongs to (nullable for MVP) | [optional] [default to undefined]
**file** | **string** | File this dataset is based on (nullable; SET_NULL preserves dataset on file deletion) | [optional] [default to undefined]
**schema_json** | **any** | Inferred schema as JSON (fields, types, nullable flags, etc.) | [optional] [readonly] [default to undefined]
**sample_data_json** | **any** | Sample data (first 100 rows) as JSON array | [optional] [readonly] [default to undefined]
**row_count** | **number** | Total number of rows in the dataset | [optional] [readonly] [default to undefined]
**format** | **string** | File format: CSV, JSON, PARQUET | [optional] [default to undefined]
**version** | **number** | Dataset version (per-asset version counter) | [optional] [readonly] [default to 1]
**parent_version** | **string** | Parent version in version tree | [optional] [readonly] [default to undefined]
**semantic_version** | **string** | Semantic version string (e.g., \&#39;1.0.0\&#39;) | [optional] [readonly] [default to undefined]
**version_tags** | **any** | Version tags (e.g., [\&#39;production\&#39;, \&#39;staging\&#39;]) | [optional] [readonly] [default to undefined]
**is_current** | **boolean** | Whether this is the current version for the asset | [optional] [readonly] [default to undefined]
**created_by** | **string** | User who created the dataset | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]
**canonical_iri** | **string** | Canonical Linked Data IRI: {SEMANTIC_BASE_IRI}/id/dataset/{id}. Stable identifier for JSON-LD dereference. See Phase 226 G7a. | [optional] [readonly] [default to undefined]
**latest_compliance_run** | **string** | Latest SUCCEEDED compliance run for this dataset (Phase 231.3). | [optional] [readonly] [default to undefined]

## Example

```typescript
import { PatchedDataset } from './api';

const instance: PatchedDataset = {
    id,
    tenant,
    asset,
    file,
    schema_json,
    sample_data_json,
    row_count,
    format,
    version,
    parent_version,
    semantic_version,
    version_tags,
    is_current,
    created_by,
    created_at,
    updated_at,
    canonical_iri,
    latest_compliance_run,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
