# JOURNEY-DPO-007: Import Data from External Provider (Federated Import)

**Persona:** [Data Protection Officer](../personas/data-protection-officer/)
**Use Cases:** UC-FED-IMPORT-001
**Phase:** 284 (GA Promotion — 284.A)
**Status:** Implemented
**E2E:** `federated-import.spec.ts`
**Routes:** `/integrations/federated-import`

## Overview

A Data Protection Officer initiates a federated import from an external data provider. The DPO browses available providers, creates an import job referencing the provider's credentials via AWS Secrets Manager ARN (never raw credentials), monitors the import job status, and verifies that imported assets pass the cross-region consent gate before entering the catalogue. Federated imports are long-running async jobs tracked through the existing `Job` model (`JobType.FEDERATED_IMPORT`).

## Journey Steps

1. **Browse providers** — Navigate to `/integrations/federated-import`. The `FederatedImportPage` renders a provider listing with provider name, supported data formats, region, and availability status. Source: `GET /api/v1/integrations/federated-import/providers/`.
2. **Create import job** — Selects a provider, fills the import form: credential reference (AWS SM ARN, never raw credentials), source dataset identifier, target asset name, optional schedule. POSTs to `POST /api/v1/integrations/federated-import/imports/` → enqueues async job → returns `Job.id`.
3. **Monitor job status** — The import detail page polls job status: PENDING → IN_PROGRESS → COMPLETED / FAILED. Shows progress indicator and elapsed time. Source: `GET /api/v1/integrations/federated-import/imports/{id}/status/`.
4. **Cross-region consent gate** — During import, `_enforce_federated_import_gates()` at `discovery_service.py:35` checks cross-region consent compliance. If the source region lacks adequate data protection, the import is blocked with a clear reason.
5. **Verify imported asset** — On COMPLETED, the DPO navigates to the newly created asset to verify metadata, compliance status, and data categories. The asset appears in the catalogue with a "Federated Import" source badge.
6. **Cancel import** — The DPO can cancel a PENDING or IN_PROGRESS import via `POST /api/v1/integrations/federated-import/imports/{id}/cancel/`.

## Error Handling

- **Credential resolution failure** — Worker cannot resolve the SM ARN → job transitions to FAILED with `CREDENTIAL_RESOLUTION_FAILED` error code.
- **Provider connectivity failure** — Job retries 3 times with exponential backoff; FAILED with `PROVIDER_UNREACHABLE` after exhaustion.
- **Cross-region consent block** — Import is rejected before data transfer begins; the DPO sees the specific regulation and clause that blocks the transfer.
- **Invalid credential_ref** — API validates ARN format at submission time; rejects with 400 before enqueuing.
- **Job timeout** — Imports exceeding 30-minute wall-clock time are marked FAILED with `TIMEOUT`.

## Audit Events

| Event | Trigger | Retention |
|---|---|---|
| `FEDERATED_IMPORT_CREATED` | New import job enqueued | 90 days |
| `FEDERATED_IMPORT_COMPLETED` | Import job succeeds | 90 days |
| `FEDERATED_IMPORT_FAILED` | Import job fails (any reason) | 90 days |
| `FEDERATED_IMPORT_CANCELLED` | Import cancelled by user | 90 days |
| `FEDERATED_IMPORT_CONSENT_BLOCKED` | Cross-region consent gate blocks import | 90 days |

## Success Criteria

- DPO can browse available providers and create an import job in under 2 minutes.
- Credential ARN is validated at submission; raw credentials never appear in API payloads, logs, or audit events.
- Import job status polls correctly through PENDING → IN_PROGRESS → COMPLETED.
- Cross-region consent gate blocks imports from non-adequate jurisdictions with a specific, actionable reason.
- All 5 audit event types are emitted on their respective triggers.

## Related

- E2E: `frontend/e2e/journeys/federated-import.spec.ts` (284.A.6)
- Runbook: [RB-COMP-006-federated-import.md](../../runbooks/RB-COMP-006-federated-import.md)
- Components: `FederatedImportPage`
- CLI: `datahub federated-import providers/import/status/cancel` (284.A.4)
- SDK: `client.federated_import.list_providers/create_import_job/get_import_status/cancel_import` (284.A.3)
- Feature flag: `federated_import_enabled` (GA, opt-in, default_new=False, requires DPO+Legal signoff)
- Backend gate: `_enforce_federated_import_gates()` at `hub/apps/integrations/services/discovery_service.py:35`
- Phase: 284.A (DRAFT→GA promotion)
