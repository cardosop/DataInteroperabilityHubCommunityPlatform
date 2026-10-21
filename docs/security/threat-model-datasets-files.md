# STRIDE Threat Model — Datasets & Files (Phase 260.2)

> **Audience**: Platform security, Engineering leads, DPO, P2 release manager.  
> **Phase**: 260.2.I.1 — closes pass-2 **S-1**.  
> **Last updated**: 2026-05-06.  
> **Status**: Launch prerequisite for datasets/files hardening track. **Pre-merge security-team sign-off REQUIRED** per 260.2.I.2 (see § Sign-off).

This document treats the **tenant-scoped Dataset and File REST surfaces** as one system: file upload lifecycle (init → multipart chunks → complete), dataset binding to files, virus scanning, metadata reads, downloads, and deletes. It assumes **`Tenant.federated_import_enabled=False`** for the default tenant posture (Phase 250.5 opt-in): file ingestion covered here is **direct upload and provider-tenant assets**, not federated marketplace pull (see [threat-model-asset-creation-federated.md](threat-model-asset-creation-federated.md) when that flag is on).

Every threat row includes **Pinned by** — a test module, code path, or explicit out-of-scope note — so mitigations are auditable.

---

## System under threat

| Component | Description |
| --------- | ----------- |
| **Endpoint** | **Files**: `GET/POST /api/v1/files/`, `GET/PATCH/DELETE /api/v1/files/{id}/`, `POST /api/v1/files/init/`, `POST /api/v1/files/{id}/complete/`, `GET /api/v1/files/{id}/download/`, chunk upload actions under `/api/v1/files/{id}/chunks/…`. **Datasets**: `GET/POST /api/v1/datasets/`, `GET/PATCH/DELETE /api/v1/datasets/{id}/`, versioning and sample routes as implemented in `DatasetViewSet`. |
| **Code path** | `hub/apps/files/views.py::FileViewSet` (retrieve uses entitlement fallback + `FILE_METADATA_VIEWED` sampling 260.2.F), `hub/apps/files/services.py::FileService`, `hub/apps/datasets/views.py::DatasetViewSet` + dataset services; marketplace `require_entitlement` for cross-tenant file reads (260.2.A); `complete_upload` magic-byte / MIME gate (260.2.B); `abandoned_multipart_cleanup` + RQ jobs; presign via `S3StorageClient`. |
| **Data** | `File` (tenant_id, storage_path, scan_status, content_sha256, metadata_json), `Dataset` (+ `DatasetVersion` links to `File`), marketplace `Entitlement` for consumer reads of provider files, audit events (`FILE_IDOR_ATTEMPT_BLOCKED`, `FILE_METADATA_VIEWED`, `FILE_FORMAT_MISMATCH_REJECTED`, malware-related gates on dataset creation). |
| **Capability flag** | `Tenant.federated_import_enabled` (default **FALSE** — this model assumes files are not imported via federated pull). `Tenant.compliance_audit_full_sampling` (260.2.F — full metadata-view audit). Plan/subscription gates for writes (`TenantSuspensionMiddleware`). |
| **Trust boundaries** | (a) Browser/SDK ↔ Hub API; (b) Hub ↔ object storage (presigned URLs); (c) consumer tenant ↔ provider tenant file rows (entitlement); (d) ClamAV / scan worker ↔ file bytes; (e) platform rate-limit middleware ↔ DRF throttles (defence in depth). |

---

## STRIDE analysis

### S — Spoofing

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| S1 | Caller impersonates another tenant via `X-Tenant-Id` without membership | `TenantScopingMiddleware` validates UUID + membership before scoping. | `hub/apps/files/tests/security/test_idor.py::FileEndpointIDORSuite` + auth middleware tests. |
| S2 | Cross-tenant file read without entitlement | Tenant-scoped queryset → 404; entitlement path audits `FILE_IDOR_ATTEMPT_BLOCKED` | `hub/apps/files/tests/security/test_idor.py` |
| S3 | API key / JWT reuse across tenants | Tokens bound to tenant context; scope checks on write paths. | JWT + API key test suites (existing auth). |

### T — Tampering

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| T1 | Upload declares `content_type` inconsistent with actual bytes (magic-byte bypass) | `complete_upload` sniffs signature; rejects with `FILE_FORMAT_MISMATCH_REJECTED` + storage cleanup. | `hub/apps/files/tests/` + 260.2.B audit path |
| T2 | Path / filename injection in audit or storage paths | `validate_filename` + audit `_sanitize_audit_payload_values`. | `hub/apps/files/validators.py`, `hub/apps/audit/utils.py` |
| T3 | Multipart ETags / part metadata tampered to corrupt object | Server validates parts on complete; abandoned uploads swept. | `abandoned_multipart_cleanup` + complete_upload tests |

### R — Repudiation

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| R1 | Operator denies accessing file metadata | `FILE_METADATA_VIEWED` (sampled or full per tenant flag). | `hub/apps/files/tests/test_file_metadata_view_audit.py` |
| R2 | Denies IDOR attempt | `FILE_IDOR_ATTEMPT_BLOCKED` with reason + tenant ids in details. | `test_idor.py` |
| R3 | Denies malware or format reject | `FILE_FORMAT_MISMATCH_REJECTED`, dataset malware gate audits. | Compliance + datasets tests |

### I — Information disclosure

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| I1 | IDOR leaks existence or fields | 404 for cross-tenant; no asset metadata in error body for blocked reads. | `test_idor.py` |
| I2 | Presigned URL exposes wrong tenant prefix | Keys derived from `storage_path` tied to tenant + file id. | `FileService` + storage client |
| I3 | Soft-deleted file visible in list | Default list excludes DELETED/DELETING; retrieve same-tenant hidden files blocked from entitlement shortcut. | `FileViewSet.get_queryset` + `_resolve_file_via_cross_tenant_entitlement` |

### D — Denial of service

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| D1 | Flood `POST /files/init/` | Per-user 60/min + per-tenant 600/min DRF throttles (260.2.E). | `hub/apps/files/tests/test_file_init_rate_limits.py` |
| D2 | Large body / connection exhaustion | Size limits in init + business rules; subscription middleware. | `test_file_size_limits.py`, `FilesBusinessRules` |
| D3 | Abandoned multipart clutter | Scheduled cleanup deletes stale multipart state. | `hub/apps/files/tests/test_abandoned_multipart_cleanup.py` |
| D4 | Scan / complete storm | Rate limits + worker concurrency (platform-wide). | Helm + compliance scan docs |

### E — Elevation of privilege

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| E1 | AUDITOR or consumer role mutates file they can list | Role gates on destroy / init / complete / upload paths. | `test_idor.py::test_auditor_cannot_destroy_file_home_tenant` + file permission patterns |
| E2 | Cross-tenant download without entitlement | Download uses same scoping + entitlement as retrieve. | IDOR suite + download tests |
| E3 | Dataset created against INFECTED / wrong scan_status file | Fail-closed dataset gate. | `hub/apps/datasets/tests/test_dataset_malware_gate.py` |

---

## Federated import disabled posture

When **`federated_import_enabled=False`** (default), tenants **must not** gain file bytes or dataset rows through federated-import code paths. Enforcement is shared with Phase 250.5:

- Asset/file creation entry points for federated flows reject at the service gate.
- **This document’s file surface** is still exposed to classic abuse (presign flood, IDOR, MIME lying) independent of federation — controls above apply.

Pinned by: `hub/apps/integrations/tests/` federated gate tests + `Tenant.federated_import_enabled` checks at service entry.

---

## Residual risks

| # | Risk | Owner | Tracking |
| - | ---- | ----- | -------- |
| RR1 | Compromised object-storage credentials allow out-of-band read of `storage_path` layout | CloudSec / S3 IAM | Bucket policy + IRSA; outside app threat model |
| RR2 | ClamAV bypass via polyglot or future engine gap | Platform security | Virus-scan E2E opt-in suite; engine updates |
| RR3 | Sampling (`FILE_METADATA_VIEWED` 90% default non-logged) limits forensic completeness | DPO + security | `compliance_audit_full_sampling` flag |

---

## Sign-off

**Required reviewers** (260.2.I.2 — **pre-merge security-team sign-off REQUIRED**):

1. Platform security lead  
2. Engineering lead — Datasets/Files domain  
3. DPO (Data Protection Officer) where PII flows exist  
4. P2 release manager  

**Status: PENDING** — Replace table entries with dated **APPROVED** (or **REJECTED** + notes) before GA. Structural CI asserts this section exists (`hub/tests/test_security_docs_phase_260_2_i.py`); it does **not** replace human review.

| Reviewer (role) | Date | Decision | Notes |
| --------------- | ---- | -------- | ----- |
| Platform security | _PENDING_ | _PENDING_ | _PENDING_ |
| Engineering — Datasets/Files | _PENDING_ | _PENDING_ | _PENDING_ |
| DPO | _PENDING_ | _PENDING_ | _PENDING_ |
| P2 release manager | _PENDING_ | _PENDING_ | _PENDING_ |
