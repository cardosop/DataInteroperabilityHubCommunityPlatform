# DomainAnalytics

Serializer for domain analytics response

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**domain_id** | **string** |  | [default to undefined]
**domain_name** | **string** |  | [default to undefined]
**status** | **string** |  | [default to undefined]
**created_at** | **string** |  | [default to undefined]
**updated_at** | **string** |  | [default to undefined]
**resource_usage** | **{ [key: string]: any; }** |  | [default to undefined]
**resource_quota** | **{ [key: string]: any; }** |  | [default to undefined]
**resource_usage_percentages** | **{ [key: string]: any; }** |  | [default to undefined]
**total_policies** | **number** |  | [default to undefined]
**applied_policies** | **number** |  | [default to undefined]
**pending_policies** | **number** |  | [default to undefined]
**compliance_status** | **string** |  | [default to undefined]
**violation_count** | **number** |  | [default to undefined]
**last_compliance_check** | **string** |  | [default to undefined]
**boundaries_count** | **number** |  | [default to undefined]
**capabilities_count** | **number** |  | [default to undefined]
**health_score** | **number** |  | [default to undefined]
**health_status** | **string** |  | [default to undefined]

## Example

```typescript
import { DomainAnalytics } from './api';

const instance: DomainAnalytics = {
    domain_id,
    domain_name,
    status,
    created_at,
    updated_at,
    resource_usage,
    resource_quota,
    resource_usage_percentages,
    total_policies,
    applied_policies,
    pending_policies,
    compliance_status,
    violation_count,
    last_compliance_check,
    boundaries_count,
    capabilities_count,
    health_score,
    health_status,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
