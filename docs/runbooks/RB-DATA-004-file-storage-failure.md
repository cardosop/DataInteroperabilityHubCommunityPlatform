# RB-DATA-004 — File Storage Failure

**Owner:** data-plane-eng@meshant.com | **Created:** 2026-05-18

## 1. Overview
File storage handles upload, presigned URLs, virus scanning, and quota enforcement for tenant files in S3/MinIO.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| File upload returns 413 | File exceeds tenant quota; `PlanLimitService.check_limit("file_size")` exceeded |
| Presigned URL generation fails | S3/MinIO unreachable; IAM credential expired |
| Virus scan stuck in PENDING | ClamAV service down; scan queue backlog |
| File download 404 | File soft-deleted; retention policy removed; `files_enabled=False` |
| Multi-part upload incomplete | Parts expired (>7 days); checksum mismatch |

## 3. Investigation
1. Check tenant quota: `GET /api/v1/tenants/me/usage/` → file_size_bytes
2. Verify S3 connectivity: `aws s3 ls s3://<bucket>/ --profile staging`
3. Check virus scan: `GET /api/v1/files/{id}/scan-status/`
4. Check file status: `GET /api/v1/files/{id}/` → status field

## 4. Remediation
- **Quota:** Upgrade tenant plan or request quota increase
- **S3:** Rotate IAM credentials; check `AWS_REGION` env var
- **Virus scan:** Restart ClamAV service; clear scan queue
- **Deleted file:** Restore from backup if within retention window

## 5. Recovery
1. Fix root cause
2. Re-upload file or restore from backup
3. Verify file accessible and scan-status returns COMPLETED

## 6. Escalation
- **P3:** Single file upload failure
- **P2:** Quota exhaustion affecting multiple tenants
- **P1:** S3/MinIO outage — all file operations failing
- **Contact:** data-plane-eng@meshant.com

## 7. Related
- `docs/runbooks/file-quota-exhaustion.md`
- `docs/runbooks/file-virus-scan-incident.md`
- `docs/runbooks/file-retention.md`
