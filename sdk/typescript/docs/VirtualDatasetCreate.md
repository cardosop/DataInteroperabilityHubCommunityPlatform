# VirtualDatasetCreate

Serializer for virtual dataset creation with comprehensive validation

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**name** | **string** | Virtual dataset name (unique per tenant) | [default to undefined]
**description** | **string** | Virtual dataset description | [optional] [default to undefined]
**query** | **string** | Query definition (SQL, SPARQL, federated query, etc.) | [default to undefined]
**query_type** | **string** | Type of query: SQL, SPARQL, FEDERATED, GRAPHQL, REST  * &#x60;SQL&#x60; - SQL Query * &#x60;SPARQL&#x60; - SPARQL Query * &#x60;FEDERATED&#x60; - Federated Query * &#x60;GRAPHQL&#x60; - GraphQL Query * &#x60;REST&#x60; - REST API Query | [default to undefined]
**schema** | **any** | Output schema definition as JSON (fields, types, constraints, etc.) | [optional] [default to undefined]
**sources** | **any** | Source system configurations as JSON array (connection details, mappings, etc.) | [optional] [default to undefined]
**version** | **string** | Virtual dataset version (semantic versioning: major.minor.patch) | [optional] [default to '1.0.0']
**status** | **string** | Virtual dataset status: DRAFT, ACTIVE, INACTIVE, ARCHIVED  * &#x60;DRAFT&#x60; - Draft * &#x60;ACTIVE&#x60; - Active * &#x60;INACTIVE&#x60; - Inactive * &#x60;ARCHIVED&#x60; - Archived | [optional] [default to StatusEnum_Draft]

## Example

```typescript
import { VirtualDatasetCreate } from './api';

const instance: VirtualDatasetCreate = {
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
