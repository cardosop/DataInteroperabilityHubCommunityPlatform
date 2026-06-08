# ComplianceReport

Serializer for ComplianceReport model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**domain_id** | **string** |  | [optional] [readonly] [default to undefined]
**domain_name** | **string** |  | [optional] [readonly] [default to undefined]
**asset_id** | **string** |  | [optional] [readonly] [default to undefined]
**asset_name** | **string** |  | [optional] [readonly] [default to undefined]
**compliance_status** | **string** | * &#x60;COMPLIANT&#x60; - Compliant * &#x60;NON_COMPLIANT&#x60; - Non-Compliant * &#x60;PARTIAL&#x60; - Partially Compliant * &#x60;UNKNOWN&#x60; - Unknown | [default to undefined]
**violations** | **any** | Violations as JSON (list of violation objects with type, severity, description, etc.) | [optional] [readonly] [default to undefined]
**violation_count** | **string** |  | [optional] [readonly] [default to undefined]
**generated_at** | **string** | Timestamp when report was generated | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { ComplianceReport } from './api';

const instance: ComplianceReport = {
    id,
    domain_id,
    domain_name,
    asset_id,
    asset_name,
    compliance_status,
    violations,
    violation_count,
    generated_at,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
