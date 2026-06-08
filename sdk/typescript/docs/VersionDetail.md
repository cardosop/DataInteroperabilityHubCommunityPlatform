# VersionDetail

Single version detail (get version by id).

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**resource_type** | **string** | * &#x60;contract&#x60; - contract * &#x60;dataset&#x60; - dataset | [optional] [readonly] [default to undefined]
**version** | **number** |  | [optional] [readonly] [default to undefined]
**semantic_version** | **string** |  | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]
**is_current** | **boolean** |  | [optional] [readonly] [default to undefined]
**status** | **string** |  | [optional] [readonly] [default to undefined]
**original_spec_version** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { VersionDetail } from './api';

const instance: VersionDetail = {
    id,
    resource_type,
    version,
    semantic_version,
    created_at,
    updated_at,
    is_current,
    status,
    original_spec_version,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
