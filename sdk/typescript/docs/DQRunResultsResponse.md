# DQRunResultsResponse


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**dq_run_id** | **string** |  | [default to undefined]
**overall_status** | **string** |  | [default to undefined]
**quality_score** | **number** |  | [default to undefined]
**score_breakdown** | **{ [key: string]: any; }** |  | [default to undefined]
**checks** | **Array&lt;any&gt;** |  | [default to undefined]
**check_details** | **Array&lt;any&gt;** |  | [default to undefined]
**trend_analysis** | **{ [key: string]: any; }** |  | [default to undefined]
**anomalies** | **Array&lt;any&gt;** |  | [default to undefined]
**recommendations** | **Array&lt;any&gt;** |  | [default to undefined]
**engine_type** | **string** |  | [default to undefined]
**engine_version** | **string** |  | [default to undefined]
**profile_key** | **string** |  | [default to undefined]
**metadata** | **{ [key: string]: any; }** |  | [default to undefined]
**started_at** | **string** |  | [default to undefined]
**completed_at** | **string** |  | [default to undefined]

## Example

```typescript
import { DQRunResultsResponse } from './api';

const instance: DQRunResultsResponse = {
    dq_run_id,
    overall_status,
    quality_score,
    score_breakdown,
    checks,
    check_details,
    trend_analysis,
    anomalies,
    recommendations,
    engine_type,
    engine_version,
    profile_key,
    metadata,
    started_at,
    completed_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
