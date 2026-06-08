# TransformationPipeline

Serializer for TransformationPipeline model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** | Unique identifier for the pipeline | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this pipeline belongs to | [optional] [readonly] [default to undefined]
**created_by** | **string** | User who created the pipeline | [optional] [readonly] [default to undefined]
**name** | **string** | Pipeline name (e.g., \&#39;Customer Data Enrichment\&#39;, \&#39;Sales Aggregation\&#39;) | [default to undefined]
**description** | **string** | Pipeline description and purpose | [optional] [default to undefined]
**pipeline_definition** | **any** | Complete pipeline definition (JSON format) including nodes, connections, transformations | [default to undefined]
**version** | **string** | Pipeline version (semantic versioning: major.minor.patch) | [optional] [default to '1.0.0']
**status** | **string** | * &#x60;DRAFT&#x60; - Draft * &#x60;ACTIVE&#x60; - Active * &#x60;INACTIVE&#x60; - Inactive * &#x60;ARCHIVED&#x60; - Archived | [optional] [readonly] [default to undefined]
**created_at** | **string** | When the pipeline was created | [optional] [readonly] [default to undefined]
**updated_at** | **string** | When the pipeline was last updated | [optional] [readonly] [default to undefined]
**metadata** | **any** | Additional metadata (tags, categories, source/target assets, etc.) | [optional] [default to undefined]

## Example

```typescript
import { TransformationPipeline } from './api';

const instance: TransformationPipeline = {
    id,
    tenant,
    created_by,
    name,
    description,
    pipeline_definition,
    version,
    status,
    created_at,
    updated_at,
    metadata,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
