# ScheduledIngestion

Serializer for ScheduledIngestion model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this scheduled ingestion belongs to | [optional] [readonly] [default to undefined]
**tenant_name** | **string** |  | [optional] [readonly] [default to undefined]
**name** | **string** |  | [default to undefined]
**description** | **string** | Optional description | [optional] [default to undefined]
**source_type** | **string** | Source type: S3, GCS, AZURE_BLOB, HTTP, FTP, SFTP, DATABASE  * &#x60;S3&#x60; - Amazon S3 * &#x60;GCS&#x60; - Google Cloud Storage * &#x60;AZURE_BLOB&#x60; - Azure Blob Storage * &#x60;HTTP&#x60; - HTTP * &#x60;HTTPS&#x60; - HTTPS * &#x60;FTP&#x60; - FTP * &#x60;SFTP&#x60; - SFTP * &#x60;DATABASE&#x60; - Database | [default to undefined]
**source_config** | **any** | Source configuration (connection details, credentials, paths) stored securely | [optional] [default to undefined]
**schedule_type** | **string** | Schedule type: DAILY, WEEKLY, MONTHLY, CUSTOM_CRON  * &#x60;DAILY&#x60; - Daily * &#x60;WEEKLY&#x60; - Weekly * &#x60;MONTHLY&#x60; - Monthly * &#x60;CUSTOM_CRON&#x60; - Custom Cron | [optional] [default to undefined]
**schedule_config** | **any** | Schedule configuration (cron expression, timezone, days of week) | [default to undefined]
**file_pattern** | **string** | File pattern (regex for matching files). Omit or leave blank to match all files (.*). | [default to undefined]
**asset** | **string** | Asset to associate ingested data with (optional) | [optional] [default to undefined]
**asset_id** | **string** |  | [optional] [default to undefined]
**asset_name** | **string** |  | [optional] [readonly] [default to undefined]
**contract** | **string** | Contract to use for ingested data (optional - can create new contract per ingestion) | [optional] [default to undefined]
**contract_name** | **string** |  | [optional] [readonly] [default to undefined]
**auto_create_asset** | **boolean** | Create asset if it doesn\&#39;t exist | [optional] [default to undefined]
**auto_activate** | **boolean** | Auto-activate asset after ingestion | [optional] [default to undefined]
**status** | **string** | Status: ACTIVE, PAUSED, ERROR  * &#x60;ACTIVE&#x60; - Active * &#x60;PAUSED&#x60; - Paused * &#x60;ERROR&#x60; - Error * &#x60;DELETED&#x60; - Deleted | [optional] [default to undefined]
**next_run_at** | **string** | Next scheduled run time (calculated based on schedule) | [optional] [readonly] [default to undefined]
**prefect_deployment_id** | **string** | Prefect deployment ID (format: {tenant_id}-{scheduled_ingestion_id}) | [optional] [readonly] [default to undefined]
**deployment_sync_status** | **string** | Prefect deployment sync status: SYNCED, PENDING, FAILED  * &#x60;SYNCED&#x60; - Synced * &#x60;PENDING&#x60; - Pending * &#x60;FAILED&#x60; - Failed | [optional] [readonly] [default to undefined]
**prefect_work_pool_name** | **string** | Prefect work pool name | [optional] [default to undefined]
**last_processed_file** | **string** | Last processed file path/key (for incremental ingestion) | [optional] [readonly] [default to undefined]
**last_processed_timestamp** | **string** | Last processed file timestamp (for incremental ingestion) | [optional] [readonly] [default to undefined]
**ingestion_state** | **any** | Ingestion state (processed files list, incremental state, etc.) | [optional] [readonly] [default to undefined]
**error_message** | **string** | Error message if status is ERROR | [optional] [readonly] [default to undefined]
**created_by** | **string** | User who created the scheduled ingestion | [optional] [default to undefined]
**created_by_username** | **string** |  | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { ScheduledIngestion } from './api';

const instance: ScheduledIngestion = {
    id,
    tenant,
    tenant_name,
    name,
    description,
    source_type,
    source_config,
    schedule_type,
    schedule_config,
    file_pattern,
    asset,
    asset_id,
    asset_name,
    contract,
    contract_name,
    auto_create_asset,
    auto_activate,
    status,
    next_run_at,
    prefect_deployment_id,
    deployment_sync_status,
    prefect_work_pool_name,
    last_processed_file,
    last_processed_timestamp,
    ingestion_state,
    error_message,
    created_by,
    created_by_username,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
