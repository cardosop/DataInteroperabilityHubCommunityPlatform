# ComplianceRun

Serializer for ComplianceRun model — exposes all v2 output fields.

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this compliance run belongs to | [optional] [readonly] [default to undefined]
**asset** | **string** | Asset this compliance run is for (nullable) | [optional] [default to undefined]
**dataset** | **string** | Dataset this compliance run is for (nullable; SET_NULL preserves audit trail) | [optional] [default to undefined]
**file** | **string** | File this compliance run is for (scan-only, nullable) | [optional] [default to undefined]
**job** | **string** | Job that orchestrates this compliance run | [optional] [readonly] [default to undefined]
**regulations** | **any** | List of applicable regulations (e.g., [\&#39;GDPR\&#39;, \&#39;LGPD\&#39;]) | [optional] [default to undefined]
**status** | **string** | Compliance run status: PENDING, QUEUED, RUNNING, SUCCEEDED, FAILED  * &#x60;PENDING&#x60; - Pending * &#x60;QUEUED&#x60; - Queued * &#x60;RUNNING&#x60; - Running * &#x60;SUCCEEDED&#x60; - Succeeded * &#x60;FAILED&#x60; - Failed | [optional] [readonly] [default to undefined]
**overall_status** | **string** | Overall compliance status: PASS, WARN, FAIL (from result) | [optional] [readonly] [default to undefined]
**risk_level** | **string** | Risk level: NONE, LOW, MEDIUM, HIGH, CRITICAL  * &#x60;NONE&#x60; - None * &#x60;LOW&#x60; - Low * &#x60;MEDIUM&#x60; - Medium * &#x60;HIGH&#x60; - High * &#x60;CRITICAL&#x60; - Critical * &#x60;UNKNOWN&#x60; - Unknown | [optional] [readonly] [default to undefined]
**allowed_to_store** | **boolean** | Whether data is allowed to be stored (NULL if check not completed) | [optional] [readonly] [default to undefined]
**detected_categories_json** | **any** | Summary of detected PII categories and counts | [optional] [readonly] [default to undefined]
**column_findings_json** | **any** | Per-column PII detection findings | [optional] [readonly] [default to undefined]
**regulation_mapping_json** | **any** | Regulatory mapping details (GDPR, LGPD, CCPA, HIPAA, SOX) | [optional] [readonly] [default to undefined]
**metadata_json** | **any** | Async job tracking metadata: {\&quot;job_id\&quot;: \&quot;...\&quot;, \&quot;poll_url\&quot;: \&quot;...\&quot;} | [optional] [readonly] [default to undefined]
**cross_border_alert** | **any** | Cross-border data transfer alert from compliance service v2 | [optional] [readonly] [default to undefined]
**localisation_alert** | **any** | Data localisation requirement alert from compliance service v2 | [optional] [readonly] [default to undefined]
**legal_basis_violations** | **any** | Legal basis violations reported by compliance service v2 | [optional] [readonly] [default to undefined]
**estimated_population_ratio** | **string** |  | [optional] [readonly] [default to undefined]
**schema_version** | **string** |  | [optional] [readonly] [default to undefined]
**regulation_summaries** | **string** |  | [optional] [readonly] [default to undefined]
**started_at** | **string** | When compliance run started | [optional] [readonly] [default to undefined]
**completed_at** | **string** | When compliance run completed | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { ComplianceRun } from './api';

const instance: ComplianceRun = {
    id,
    tenant,
    asset,
    dataset,
    file,
    job,
    regulations,
    status,
    overall_status,
    risk_level,
    allowed_to_store,
    detected_categories_json,
    column_findings_json,
    regulation_mapping_json,
    metadata_json,
    cross_border_alert,
    localisation_alert,
    legal_basis_violations,
    estimated_population_ratio,
    schema_version,
    regulation_summaries,
    started_at,
    completed_at,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
