# VirtualDatasetVersion

Serializer for virtual dataset version information

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**version** | **string** | Version string | [default to undefined]
**status** | **string** | Status of this version | [default to undefined]
**created_at** | **string** | When this version was created | [default to undefined]
**updated_at** | **string** | When this version was last updated | [default to undefined]
**query_type** | **string** | Query type for this version | [default to undefined]
**source_count** | **number** | Number of sources in this version | [default to undefined]

## Example

```typescript
import { VirtualDatasetVersion } from './api';

const instance: VirtualDatasetVersion = {
    version,
    status,
    created_at,
    updated_at,
    query_type,
    source_count,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
