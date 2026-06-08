# UserNotification

Read-optimised serializer for list + detail endpoints.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this notification belongs to | [optional] [readonly] [default to undefined]
**user** | **string** | Recipient | [optional] [readonly] [default to undefined]
**audit_event** | **string** | Optional link to the underlying audit event | [optional] [readonly] [default to undefined]
**title** | **string** |  | [optional] [readonly] [default to undefined]
**message** | **string** |  | [optional] [readonly] [default to undefined]
**notification_type** | **string** | * &#x60;INFO&#x60; - Info * &#x60;SUCCESS&#x60; - Success * &#x60;WARNING&#x60; - Warning * &#x60;ERROR&#x60; - Error | [optional] [readonly] [default to undefined]
**category** | **string** | * &#x60;GOVERNANCE&#x60; - Governance * &#x60;MARKETPLACE&#x60; - Marketplace * &#x60;JOBS&#x60; - Jobs * &#x60;CONTRACTS&#x60; - Contracts * &#x60;SYSTEM&#x60; - System * &#x60;LINEAGE_IMPACT&#x60; - Lineage Impact | [optional] [readonly] [default to undefined]
**resource_type** | **string** | Resource type the notification points at (matches AuditEvent.resource_type) | [optional] [readonly] [default to undefined]
**resource_id** | **string** | Resource UUID the notification points at | [optional] [readonly] [default to undefined]
**read** | **boolean** |  | [optional] [readonly] [default to undefined]
**read_at** | **string** |  | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { UserNotification } from './api';

const instance: UserNotification = {
    id,
    tenant,
    user,
    audit_event,
    title,
    message,
    notification_type,
    category,
    resource_type,
    resource_id,
    read,
    read_at,
    created_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
