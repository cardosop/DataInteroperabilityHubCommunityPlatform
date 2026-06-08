# Job

Serializer for Job model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this job belongs to (nullable for system jobs) | [optional] [readonly] [default to undefined]
**type** | **string** | Job type: DQ_RUN, COMPLIANCE_RUN, CONTRACT_VALIDATION, etc.  * &#x60;DQ_RUN&#x60; - Data Quality Run * &#x60;COMPLIANCE_RUN&#x60; - Compliance Run * &#x60;CONTRACT_VALIDATION&#x60; - Contract Validation * &#x60;SEMANTIC_MAPPING&#x60; - Semantic Mapping * &#x60;CONTRACT_MIGRATION&#x60; - Contract Migration * &#x60;SCHEDULED_INGESTION&#x60; - Scheduled Ingestion * &#x60;RETENTION_POLICY_ENFORCEMENT&#x60; - Retention Policy Enforcement * &#x60;SEARCH_INDEX_UPDATE&#x60; - Search Index Update * &#x60;ODPS_NORMALIZATION&#x60; - ODPS Normalization * &#x60;ODPS_REF_RESOLUTION&#x60; - ODPS $ref Resolution * &#x60;ODPS_EXPORT&#x60; - ODPS Export * &#x60;ODPS_SEMANTIC_MAPPING&#x60; - ODPS Semantic Mapping * &#x60;ODPS_LINKING&#x60; - ODPS Linking * &#x60;VIRTUAL_QUERY_EXECUTION&#x60; - Virtual Query Execution * &#x60;MARKETPLACE_SYNC&#x60; - Marketplace Sync * &#x60;ML_TRAINING&#x60; - ML Training * &#x60;ML_INFERENCE&#x60; - ML Inference * &#x60;TRANSFORMATION&#x60; - Transformation Pipeline * &#x60;SEMANTIC_EXPORT_LARGE&#x60; - Semantic Export (large) * &#x60;SEMANTIC_SNAPSHOT&#x60; - Semantic Snapshot * &#x60;ONTOLOGY_VALIDATE&#x60; - Ontology Validate * &#x60;LDN_OUTBOUND_DELIVERY&#x60; - LDN Outbound Delivery | [default to undefined]
**status** | **string** | Job status: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED  * &#x60;PENDING&#x60; - Pending * &#x60;RUNNING&#x60; - Running * &#x60;COMPLETED&#x60; - Completed * &#x60;FAILED&#x60; - Failed * &#x60;CANCELLED&#x60; - Cancelled | [optional] [readonly] [default to undefined]
**resource_type** | **string** | Resource type: CONTRACT, DATASET, FILE, ASSET, etc. | [default to undefined]
**resource_id** | **string** | ID of the resource this job operates on | [default to undefined]
**created_by** | **string** | User who created the job | [optional] [readonly] [default to undefined]
**started_at** | **string** | When job started running | [optional] [readonly] [default to undefined]
**completed_at** | **string** | When job completed (success or failure) | [optional] [readonly] [default to undefined]
**error_message** | **string** | Error message if job failed | [optional] [readonly] [default to undefined]
**result_json** | **any** | Job result data (partial results supported) | [optional] [readonly] [default to undefined]
**details_json** | **any** | Job details (engine versions, progress, etc.) | [optional] [default to undefined]
**timeout_seconds** | **number** | Job timeout in seconds (configurable per job type) | [optional] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { Job } from './api';

const instance: Job = {
    id,
    tenant,
    type,
    status,
    resource_type,
    resource_id,
    created_by,
    started_at,
    completed_at,
    error_message,
    result_json,
    details_json,
    timeout_seconds,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
