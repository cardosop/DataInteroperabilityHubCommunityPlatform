# VersionCompare

Compare two versions response.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id_a** | **string** |  | [optional] [readonly] [default to undefined]
**id_b** | **string** |  | [optional] [readonly] [default to undefined]
**resource_type** | **string** | * &#x60;contract&#x60; - contract * &#x60;dataset&#x60; - dataset | [optional] [readonly] [default to undefined]
**version_a** | **number** |  | [optional] [readonly] [default to undefined]
**version_b** | **number** |  | [optional] [readonly] [default to undefined]
**created_at_a** | **string** |  | [optional] [readonly] [default to undefined]
**created_at_b** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { VersionCompare } from './api';

const instance: VersionCompare = {
    id_a,
    id_b,
    resource_type,
    version_a,
    version_b,
    created_at_a,
    created_at_b,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
