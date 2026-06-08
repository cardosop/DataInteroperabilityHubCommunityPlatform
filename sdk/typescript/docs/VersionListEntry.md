# VersionListEntry

One entry in the list versions response.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**resource_type** | **string** | * &#x60;contract&#x60; - contract * &#x60;dataset&#x60; - dataset | [optional] [readonly] [default to undefined]
**version** | **number** |  | [optional] [readonly] [default to undefined]
**semantic_version** | **string** |  | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**is_current** | **boolean** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { VersionListEntry } from './api';

const instance: VersionListEntry = {
    id,
    resource_type,
    version,
    semantic_version,
    created_at,
    is_current,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
