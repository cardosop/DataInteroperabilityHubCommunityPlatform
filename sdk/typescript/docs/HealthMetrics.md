# HealthMetrics

Serializer for domain health metrics

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**health_score** | **number** | Health score (0-100) | [default to undefined]
**policy_count** | **number** | Number of applied policies | [default to undefined]
**compliance_status** | **string** | Compliance status  * &#x60;COMPLIANT&#x60; - Compliant * &#x60;NON_COMPLIANT&#x60; - Non-Compliant * &#x60;PARTIAL&#x60; - Partially Compliant * &#x60;UNKNOWN&#x60; - Unknown | [default to undefined]
**violation_count** | **number** | Number of violations | [default to undefined]
**is_active** | **boolean** | Whether domain is active | [default to undefined]

## Example

```typescript
import { HealthMetrics } from './api';

const instance: HealthMetrics = {
    health_score,
    policy_count,
    compliance_status,
    violation_count,
    is_active,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
