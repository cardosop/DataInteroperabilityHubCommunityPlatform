# RB-FILES-001 — File Upload Failure

**Owner:** data-platform@meshant.com | **Created:** 2026-05-20

## 1. Overview
File upload subsystem handles multipart uploads to S3 with magic-byte validation, encoding detection, and checksum verification. Failures span upload initiation, part upload, completion, and post-upload processing.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| `FILE_FORMAT_MISMATCH` | Declared Content-Type disagrees with magic-byte sniff |
| `FILE_ENCODING_UNSUPPORTED` | Charset detection confidence < 0.9 |
| `MULTIPART_INCOMPLETE` | S3 missing part numbers; transient transport failure |
| `MULTIPART_UPLOAD_NO_LONGER_EXISTS` | S3 upload session aborted or expired |
| `FILE_TOO_LARGE_FOR_INFERENCE` | File exceeds DATASET_INFERENCE_MAX_BYTES |
| `FILES_DISABLED` | Tenant files_enabled flag is off |

## 3. Investigation
1. Check file status: `GET /api/v1/files/{id}/`
2. Check S3 multipart status via AWS Console or `aws s3api list-parts`
3. Verify tenant flag: `GET /api/v1/admin/tenants/{id}/feature-flags/`
4. Check magic-byte detection logs for format mismatches

## 4. Remediation
- **Format mismatch:** Re-upload with correct MIME type
- **Encoding:** Re-encode as UTF-8 or use binary format (Parquet)
- **Multipart incomplete:** Re-upload only missing part numbers from `details.missing_parts`
- **Upload expired:** Re-initialize via `POST /files/init/`

## 5. Recovery
1. Identify failure from error code in response
2. Apply remediation per error type
3. Re-upload file
4. Verify file reaches ACTIVE status

## 6. Escalation
| Priority | Condition | Contact |
|----------|-----------|---------|
| P3 | Single file upload failure | Tenant admin |
| P2 | All uploads failing for a tenant | data-platform@meshant.com |
| P1 | S3 bucket inaccessible | Infrastructure on-call |

## 7. Related
- `docs/runbooks/magic-byte-mismatch-spike.md`
- `docs/runbooks/file-orphan-cleanup.md`
- `hub/apps/files/storage.py`
- `hub/apps/files/views.py`
