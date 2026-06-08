# AuditEvent

Serializer for audit events

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this event belongs to (null for platform-level events) | [optional] [readonly] [default to undefined]
**tenant_name** | **string** |  | [optional] [readonly] [default to undefined]
**actor_user** | **string** | User who performed the action (null for system events) | [optional] [readonly] [default to undefined]
**actor_user_email** | **string** |  | [optional] [readonly] [default to undefined]
**resource_type** | **string** | Type of resource (e.g., TENANT, USER, CONTRACT, ASSET, AUTH) | [optional] [readonly] [default to undefined]
**resource_id** | **string** | ID of the resource (null for resource-less events) | [optional] [readonly] [default to undefined]
**action** | **string** | Action performed (e.g., CREATED, UPDATED, DELETED, LOGIN, LOGOUT) | [optional] [readonly] [default to undefined]
**result** | **string** | Result of the action  * &#x60;SUCCESS&#x60; - Success * &#x60;FAILURE&#x60; - Failure * &#x60;WARNING&#x60; - Warning | [optional] [readonly] [default to undefined]
**details_json** | **any** | Additional details as JSON (no PII allowed) | [optional] [readonly] [default to undefined]
**timestamp** | **string** | When the event occurred (UTC) | [optional] [readonly] [default to undefined]

## Example

```typescript
import { AuditEvent } from './api';

const instance: AuditEvent = {
    id,
    tenant,
    tenant_name,
    actor_user,
    actor_user_email,
    resource_type,
    resource_id,
    action,
    result,
    details_json,
    timestamp,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
