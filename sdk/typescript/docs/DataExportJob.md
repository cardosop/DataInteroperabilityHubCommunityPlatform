# DataExportJob

Serializer for DataExportJob model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**user** | **string** | User requesting data export | [optional] [readonly] [default to undefined]
**tenant** | **string** | Tenant this export belongs to | [optional] [readonly] [default to undefined]
**status** | **string** | Export job status  * &#x60;PENDING&#x60; - Pending * &#x60;PROCESSING&#x60; - Processing * &#x60;COMPLETED&#x60; - Completed * &#x60;FAILED&#x60; - Failed | [optional] [default to undefined]
**storage_path** | **string** | Path in storage (S3/MinIO) for export archive | [optional] [readonly] [default to undefined]
**download_url** | **string** | Signed URL for downloading export (short-lived); presigned URLs can exceed 2KB | [optional] [readonly] [default to undefined]
**download_url_expires_at** | **string** | When download URL expires | [optional] [readonly] [default to undefined]
**error_message** | **string** | Error message if status is FAILED | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]
**completed_at** | **string** | When export was completed | [optional] [readonly] [default to undefined]

## Example

```typescript
import { DataExportJob } from './api';

const instance: DataExportJob = {
    id,
    user,
    tenant,
    status,
    storage_path,
    download_url,
    download_url_expires_at,
    error_message,
    created_at,
    updated_at,
    completed_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
