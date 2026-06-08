# PatchedDQRun

Serializer for DQRun model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this DQ run belongs to | [optional] [readonly] [default to undefined]
**asset** | **string** | Asset this DQ run is for (nullable) | [optional] [default to undefined]
**dataset** | **string** | Dataset this DQ run is for (nullable; SET_NULL preserves audit trail) | [optional] [default to undefined]
**file** | **string** | File this DQ run is for (scan-only, nullable) | [optional] [default to undefined]
**job** | **string** | Job that orchestrates this DQ run | [optional] [readonly] [default to undefined]
**profile_key** | **string** | DQ profile key (e.g., intake_basic_gx, intake_basic_soda) | [optional] [default to undefined]
**engine** | **string** | DQ engine used: GREAT_EXPECTATIONS or SODA  * &#x60;GREAT_EXPECTATIONS&#x60; - Great Expectations * &#x60;SODA&#x60; - Soda | [optional] [default to undefined]
**status** | **string** | DQ run status: PENDING, RUNNING, SUCCEEDED, FAILED  * &#x60;PENDING&#x60; - Pending * &#x60;RUNNING&#x60; - Running * &#x60;SUCCEEDED&#x60; - Succeeded * &#x60;FAILED&#x60; - Failed | [optional] [readonly] [default to undefined]
**overall_status** | **string** | Overall DQ status: PASS, FAIL, WARN, UNKNOWN (from result) | [optional] [readonly] [default to undefined]
**quality_score** | **number** | Quality score (0-100) | [optional] [readonly] [default to undefined]
**checks_json** | **any** | List of DQ checks with results | [optional] [readonly] [default to undefined]
**details_json** | **any** | Detailed DQ results and metadata | [optional] [readonly] [default to undefined]
**started_at** | **string** | When DQ run started | [optional] [readonly] [default to undefined]
**completed_at** | **string** | When DQ run completed | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { PatchedDQRun } from './api';

const instance: PatchedDQRun = {
    id,
    tenant,
    asset,
    dataset,
    file,
    job,
    profile_key,
    engine,
    status,
    overall_status,
    quality_score,
    checks_json,
    details_json,
    started_at,
    completed_at,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
