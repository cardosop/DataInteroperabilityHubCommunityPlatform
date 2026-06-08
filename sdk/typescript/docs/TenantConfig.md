# TenantConfig

Serializer for TenantConfig model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**tenant_id** | **string** |  | [optional] [readonly] [default to undefined]
**default_dq_profile** | **string** | Default DQ profile key (e.g., intake_basic_gx, intake_basic_soda) | [optional] [default to undefined]
**allowed_compliance_regimes** | **any** | List of compliance regimes available to this tenant (e.g., [\&#39;GDPR\&#39;, \&#39;LGPD\&#39;, \&#39;CCPA\&#39;]) | [optional] [default to undefined]
**default_compliance_regimes** | **any** | Default compliance regimes applied to intake flows (subset of allowed_compliance_regimes) | [optional] [default to undefined]
**compliance_risk_threshold** | **string** | Maximum acceptable compliance risk level for publishing listings and activating assets; risk strictly above this threshold blocks publish/activation.  * &#x60;NONE&#x60; - None * &#x60;LOW&#x60; - Low * &#x60;MEDIUM&#x60; - Medium * &#x60;HIGH&#x60; - High * &#x60;CRITICAL&#x60; - Critical | [optional] [default to undefined]
**data_retention_days** | **number** | Data retention period in days (90-3650) | [optional] [default to undefined]
**rate_limits** | [**{ [key: string]: RateLimits; }**](RateLimits.md) | Per-endpoint category rate limits | [optional] [default to undefined]
**max_file_size_bytes** | **number** | Maximum file size for uploads in bytes | [optional] [default to undefined]
**max_job_concurrency** | **number** | Maximum concurrent running jobs for this tenant | [optional] [default to undefined]
**max_queued_jobs** | **number** | Maximum queued jobs for this tenant | [optional] [default to undefined]
**trust_signals_enabled** | **boolean** | Enable trust signals (badges, quality SLAs) for marketplace listings | [optional] [default to undefined]
**versioning_enabled** | **boolean** | Enable dataset versioning (semantic versions, version history) for this tenant | [optional] [default to undefined]
**workflows_enabled** | **boolean** | Enable workflow orchestration for this tenant | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { TenantConfig } from './api';

const instance: TenantConfig = {
    tenant_id,
    default_dq_profile,
    allowed_compliance_regimes,
    default_compliance_regimes,
    compliance_risk_threshold,
    data_retention_days,
    rate_limits,
    max_file_size_bytes,
    max_job_concurrency,
    max_queued_jobs,
    trust_signals_enabled,
    versioning_enabled,
    workflows_enabled,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
