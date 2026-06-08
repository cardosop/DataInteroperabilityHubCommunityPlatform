# PatchedMarketplaceSyncJob

Serializer for MarketplaceSyncJob model (read operations).

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** | Unique identifier for the sync job | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant ID | [optional] [readonly] [default to undefined]
**tenant_name** | **string** | Tenant name | [optional] [readonly] [default to undefined]
**connection_id** | **string** | Connection ID | [optional] [readonly] [default to undefined]
**connection_name** | **string** | Connection name | [optional] [readonly] [default to undefined]
**direction** | **string** | Sync direction: PUSH, PULL, or BIDIRECTIONAL  * &#x60;PUSH&#x60; - Push * &#x60;PULL&#x60; - Pull * &#x60;BIDIRECTIONAL&#x60; - Bidirectional | [optional] [default to undefined]
**direction_display** | **string** | Human-readable sync direction | [optional] [readonly] [default to undefined]
**status** | **string** | Sync job status: PENDING, RUNNING, COMPLETED, FAILED, PARTIAL  * &#x60;PENDING&#x60; - Pending * &#x60;RUNNING&#x60; - Running * &#x60;COMPLETED&#x60; - Completed * &#x60;FAILED&#x60; - Failed * &#x60;PARTIAL&#x60; - Partial | [optional] [default to undefined]
**status_display** | **string** | Human-readable sync status | [optional] [readonly] [default to undefined]
**items_synced** | **number** | Number of items successfully synced | [optional] [readonly] [default to undefined]
**items_failed** | **number** | Number of items that failed to sync | [optional] [readonly] [default to undefined]
**errors** | **any** | List of error messages encountered during sync | [optional] [readonly] [default to undefined]
**metadata** | **any** | Additional metadata about the sync operation | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]
**completed_at** | **string** | When the sync job completed (success or failure) | [optional] [readonly] [default to undefined]

## Example

```typescript
import { PatchedMarketplaceSyncJob } from './api';

const instance: PatchedMarketplaceSyncJob = {
    id,
    tenant,
    tenant_name,
    connection_id,
    connection_name,
    direction,
    direction_display,
    status,
    status_display,
    items_synced,
    items_failed,
    errors,
    metadata,
    created_at,
    updated_at,
    completed_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
