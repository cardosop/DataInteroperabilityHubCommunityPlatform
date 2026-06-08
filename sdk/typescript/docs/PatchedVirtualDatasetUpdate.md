# PatchedVirtualDatasetUpdate

Serializer for virtual dataset update with comprehensive validation

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**name** | **string** | Virtual dataset name (empty/whitespace rejected by service layer) | [optional] [default to undefined]
**description** | **string** | Virtual dataset description | [optional] [default to undefined]
**query** | **string** | Query definition | [optional] [default to undefined]
**query_type** | **string** | Type of query  * &#x60;SQL&#x60; - SQL Query * &#x60;SPARQL&#x60; - SPARQL Query * &#x60;FEDERATED&#x60; - Federated Query * &#x60;GRAPHQL&#x60; - GraphQL Query * &#x60;REST&#x60; - REST API Query | [optional] [default to undefined]
**schema** | **any** | Output schema definition | [optional] [default to undefined]
**sources** | **any** | Source system configurations | [optional] [default to undefined]
**version** | **string** | Virtual dataset version (semantic versioning: major.minor.patch) | [optional] [default to undefined]
**status** | **string** | Virtual dataset status  * &#x60;DRAFT&#x60; - Draft * &#x60;ACTIVE&#x60; - Active * &#x60;INACTIVE&#x60; - Inactive * &#x60;ARCHIVED&#x60; - Archived | [optional] [default to undefined]

## Example

```typescript
import { PatchedVirtualDatasetUpdate } from './api';

const instance: PatchedVirtualDatasetUpdate = {
    name,
    description,
    query,
    query_type,
    schema,
    sources,
    version,
    status,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
