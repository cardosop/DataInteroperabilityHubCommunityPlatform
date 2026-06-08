# PatchedFile

Serializer for File model

## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**id** | **string** |  | [optional] [readonly] [default to undefined]
**name** | **string** | Original filename | [optional] [default to undefined]
**content_type** | **string** | MIME type (e.g., text/csv, application/json) | [optional] [default to undefined]
**size** | **number** | File size in bytes | [optional] [default to undefined]
**content_sha256** | **string** | SHA-256 hash of file content (for deduplication and integrity) | [optional] [readonly] [default to undefined]
**status** | **string** | File status: PENDING, UPLOADING, ACTIVE, FAILED, DELETED  * &#x60;PENDING&#x60; - Pending * &#x60;UPLOADING&#x60; - Uploading * &#x60;ACTIVE&#x60; - Active * &#x60;COMPLETED&#x60; - Completed * &#x60;FAILED&#x60; - Failed * &#x60;DELETED&#x60; - Deleted | [optional] [readonly] [default to undefined]
**scan_status** | **string** | Malware scan status (ClamAV); independent of upload status  * &#x60;PENDING_SCAN&#x60; - Pending scan * &#x60;CLEAN&#x60; - Clean * &#x60;INFECTED&#x60; - Infected * &#x60;SCAN_UNAVAILABLE&#x60; - Scan unavailable * &#x60;SCAN_ERROR&#x60; - Scan error | [optional] [readonly] [default to undefined]
**scanned_at** | **string** | When the last malware scan finished (any outcome) | [optional] [readonly] [default to undefined]
**metadata_json** | **any** | Additional metadata (upload method, chunk info, etc.) | [optional] [readonly] [default to undefined]
**created_by** | **string** | User who uploaded the file | [optional] [readonly] [default to undefined]
**created_at** | **string** |  | [optional] [readonly] [default to undefined]
**updated_at** | **string** |  | [optional] [readonly] [default to undefined]

## Example

```typescript
import { PatchedFile } from './api';

const instance: PatchedFile = {
    id,
    name,
    content_type,
    size,
    content_sha256,
    status,
    scan_status,
    scanned_at,
    metadata_json,
    created_by,
    created_at,
    updated_at,
};
```

[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)
