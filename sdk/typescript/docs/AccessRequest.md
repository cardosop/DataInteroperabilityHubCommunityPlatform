# AccessRequest

Serializer for AccessRequest

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this access request belongs to | [optional] [readonly] [default to undefined]
**requested_by** | **string** | User requesting access | [optional] [readonly] [default to undefined]
**asset** | **string** | Asset access is requested for (nullable) | [optional] [default to undefined]
**dataset** | **string** | Dataset access is requested for (nullable) | [optional] [default to undefined]
**file** | **string** | File access is requested for (nullable) | [optional] [default to undefined]
**reason** | **string** | Reason for access request | [default to undefined]
**requested_access_type** | **string** | Type of access requested (e.g., \&#39;READ\&#39;, \&#39;WRITE\&#39;, \&#39;DOWNLOAD\&#39;) | [default to undefined]
**status** | **string** | Access request status  * &#x60;PENDING&#x60; - Pending * &#x60;APPROVED&#x60; - Approved * &#x60;REJECTED&#x60; - Rejected * &#x60;EXPIRED&#x60; - Expired * &#x60;REVOKED&#x60; - Revoked | [optional] [default to undefined]
**requires_approval** | **boolean** | Whether request requires approval | [optional] [default to undefined]
**approval_workflow** | **any** | Approval workflow steps (for multi-step approval) | [optional] [default to undefined]
**current_approval_step** | **number** | Current approval step index | [optional] [default to undefined]
**approvers** | **any** | List of approver user IDs | [optional] [default to undefined]
**approved_by** | **string** | User who approved this request | [optional] [readonly] [default to undefined]
**approved_at** | **string** | When request was approved | [optional] [readonly] [default to undefined]
**rejected_by** | **string** | User who rejected this request | [optional] [readonly] [default to undefined]
**rejected_at** | **string** | When request was rejected | [optional] [readonly] [default to undefined]
**rejection_reason** | **string** | Reason for rejection | [optional] [default to undefined]
**expires_at** | **string** | When access expires (nullable for permanent access) | [optional] [default to undefined]
**access_granted_at** | **string** | When access was granted | [optional] [readonly] [default to undefined]
**order** | **string** | Marketplace order that triggered this access request | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { AccessRequest } from './api';

const instance: AccessRequest = {
    id,
    tenant,
    requested_by,
    asset,
    dataset,
    file,
    reason,
    requested_access_type,
    status,
    requires_approval,
    approval_workflow,
    current_approval_step,
    approvers,
    approved_by,
    approved_at,
    rejected_by,
    rejected_at,
    rejection_reason,
    expires_at,
    access_granted_at,
    order,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
