# ErasureRequest

Serializer for ErasureRequest model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**user** | **string** | User requesting erasure | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this erasure belongs to | [optional] [readonly] [default to undefined]
**status** | **string** | Erasure request status  * &#x60;PENDING&#x60; - Pending * &#x60;PROCESSING&#x60; - Processing * &#x60;COMPLETED&#x60; - Completed * &#x60;FAILED&#x60; - Failed | [optional] [readonly] [default to undefined]
**requested_at** | **string** | When erasure was requested | [optional] [readonly] [default to undefined]
**completed_at** | **string** | When erasure was completed | [optional] [readonly] [default to undefined]
**error_message** | **string** | Error message if status is FAILED | [optional] [readonly] [default to undefined]
**anonymized_fields** | **any** | List of fields that were anonymized (not deleted) | [optional] [readonly] [default to undefined]
**deleted_resources** | **any** | List of resource types that were deleted | [optional] [readonly] [default to undefined]
**retention_exceptions** | **any** | List of resources retained due to legal/compliance requirements | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { ErasureRequest } from './api';

const instance: ErasureRequest = {
    id,
    user,
    tenant,
    status,
    requested_at,
    completed_at,
    error_message,
    anonymized_fields,
    deleted_resources,
    retention_exceptions,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
