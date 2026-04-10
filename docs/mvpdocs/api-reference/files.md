# Meshant Files API

The Files API handles binary file upload, download, and management on the
Meshant platform. Files are stored in tenant-scoped object storage and can
be attached to datasets, contracts, or compliance reports.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/files/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /files/ | List uploaded files in the current tenant |
| POST | /files/ | Upload a new file (multipart/form-data) |
| GET | /files/{id}/ | Get file metadata by ID |
| GET | /files/{id}/download/ | Download the file content |
| DELETE | /files/{id}/ | Delete a file permanently |
| POST | /files/presign/ | Generate a pre-signed upload URL for large files |
| POST | /files/{id}/complete/ | Finalize a multi-part upload |

## Request / Response Examples

### POST /files/

Upload using `multipart/form-data`:

```
Content-Type: multipart/form-data; boundary=----boundary
------boundary
Content-Disposition: form-data; name="file"; filename="sales_2026.csv"
Content-Type: text/csv

id,amount,date
1,250.00,2026-01-15
...
------boundary--
```

**Response 201:**

```json
{
  "id": "file_aaa111",
  "filename": "sales_2026.csv",
  "content_type": "text/csv",
  "size_bytes": 10485760,
  "checksum_sha256": "e3b0c44298fc...",
  "uploaded_by": "usr_abc123",
  "created_at": "2026-04-09T10:00:00Z"
}
```

### POST /files/presign/

**Request body:**

```json
{
  "filename": "warehouse_dump.parquet",
  "content_type": "application/octet-stream",
  "size_bytes": 536870912
}
```

**Response 200:**

```json
{
  "upload_id": "upl_xyz",
  "presigned_url": "https://meshant-internal.example.com/...",
  "expires_at": "2026-04-09T11:00:00Z"
}
```

## Common Parameters

- `page` (int) -- Page number for pagination.
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `content_type` (string) -- Filter by MIME type.
- `filename` (string) -- Filter by filename substring.

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 400 | `FILE_TOO_LARGE` | File exceeds the tenant's upload size limit |
| 404 | `FILE_NOT_FOUND` | File ID does not exist |
| 409 | `FILE_UPLOAD_INCOMPLETE` | Multi-part upload has not been finalized |
| 415 | `FILE_TYPE_UNSUPPORTED` | MIME type is not allowed by tenant policy |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub files`](../cli-reference/files.md)
- SDK: [`FilesAPI`](../sdk-reference/python/files.md)
