# ComplianceRunResultsResponse


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**compliance_run_id** | **string** |  | [default to undefined]
**overall_status** | **string** |  | [default to undefined]
**risk_level** | **string** |  | [default to undefined]
**allowed_to_store** | **boolean** |  | [default to undefined]
**compliance_score** | **number** |  | [default to undefined]
**score_breakdown** | **{ [key: string]: any; }** |  | [default to undefined]
**violations** | **Array&lt;any&gt;** |  | [default to undefined]
**violation_details** | **Array&lt;any&gt;** |  | [default to undefined]
**remediation_suggestions** | **Array&lt;any&gt;** |  | [default to undefined]
**risk_assessment** | **{ [key: string]: any; }** |  | [default to undefined]
**violation_timeline** | **Array&lt;any&gt;** |  | [default to undefined]
**regulations** | **Array&lt;any&gt;** |  | [default to undefined]
**detected_categories** | **{ [key: string]: any; }** |  | [default to undefined]
**column_findings** | **Array&lt;any&gt;** |  | [default to undefined]
**started_at** | **string** |  | [default to undefined]
**completed_at** | **string** |  | [default to undefined]
**cross_border_alert** | **{ [key: string]: any; }** |  | [optional] [default to undefined]
**localisation_alert** | **{ [key: string]: any; }** |  | [optional] [default to undefined]
**legal_basis_violations** | **Array&lt;any&gt;** |  | [optional] [default to undefined]
**regulation_summaries** | **Array&lt;any&gt;** |  | [optional] [default to undefined]

## Example

```typescript
import { ComplianceRunResultsResponse } from './api';

const instance: ComplianceRunResultsResponse = {
    compliance_run_id,
    overall_status,
    risk_level,
    allowed_to_store,
    compliance_score,
    score_breakdown,
    violations,
    violation_details,
    remediation_suggestions,
    risk_assessment,
    violation_timeline,
    regulations,
    detected_categories,
    column_findings,
    started_at,
    completed_at,
    cross_border_alert,
    localisation_alert,
    legal_basis_violations,
    regulation_summaries,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
