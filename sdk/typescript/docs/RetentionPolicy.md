# RetentionPolicy

Serializer for RetentionPolicy

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this retention policy belongs to | [optional] [readonly] [default to undefined]
**name** | **string** | Policy name | [default to undefined]
**description** | **string** | Policy description | [optional] [default to undefined]
**asset** | **string** | Asset this policy applies to (nullable) | [optional] [default to undefined]
**dataset** | **string** | Dataset this policy applies to (nullable) | [optional] [default to undefined]
**file** | **string** | File this policy applies to (nullable) | [optional] [default to undefined]
**policy_type** | **string** | Policy type: TIME_BASED or EVENT_BASED  * &#x60;TIME_BASED&#x60; - Time-Based * &#x60;EVENT_BASED&#x60; - Event-Based | [default to undefined]
**retention_period_days** | **number** | Retention period in days (for time-based policies) | [optional] [default to undefined]
**event_trigger** | **string** | Event trigger (e.g., \&#39;contract_expired\&#39;, \&#39;project_completed\&#39;) | [optional] [default to undefined]
**action** | **string** | Action to take when retention period expires  * &#x60;SOFT_DELETE&#x60; - Soft Delete * &#x60;HARD_DELETE&#x60; - Hard Delete * &#x60;ARCHIVE&#x60; - Archive | [optional] [default to undefined]
**grace_period_days** | **number** | Grace period in days before hard delete (for soft delete) | [optional] [default to undefined]
**legal_hold** | **boolean** | Whether data is under legal hold (prevents deletion) | [optional] [default to undefined]
**legal_hold_reason** | **string** | Reason for legal hold | [optional] [default to undefined]
**legal_hold_expires_at** | **string** | When legal hold expires (nullable for indefinite hold) | [optional] [default to undefined]
**enabled** | **boolean** | Whether policy is enabled | [optional] [default to undefined]
**last_enforced_at** | **string** | When policy was last enforced | [optional] [readonly] [default to undefined]
**created_by** | **string** | User who created this policy | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { RetentionPolicy } from './api';

const instance: RetentionPolicy = {
    id,
    tenant,
    name,
    description,
    asset,
    dataset,
    file,
    policy_type,
    retention_period_days,
    event_trigger,
    action,
    grace_period_days,
    legal_hold,
    legal_hold_reason,
    legal_hold_expires_at,
    enabled,
    last_enforced_at,
    created_by,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
