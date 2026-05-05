# SDK DE-1 coverage audit

**Audit task**: Phase 250.4.1 (closes Phase 250.0.8 partial deliverable)
**Audit date**: 2026-04-30 (deliverable filename pinned by spec)
**Auditor**: Phase 250.4 SDK programmatic-flow pre-flight
**Scope**: Enumerate the SDK methods required for the DE-1
"programmatic asset creation" persona-journey vs the canonical
hub POST sequence; identify gaps that block a CLI/SDK consumer
from completing the journey end-to-end without falling back to
raw HTTP.

## DE-1 canonical POST sequence (server side)

The DE-1 journey is captured in
[openspec/changes/preprod01/specs/cli-sdk-mvp-coverage-parity/spec.md](../../openspec/changes/preprod01/specs/cli-sdk-mvp-coverage-parity/spec.md).
Mapped to hub endpoints:

| # | Step | HTTP | Endpoint | Async? |
| --- | --- | --- | --- | --- |
| 1 | Create contract from ODPS payload | POST | `/api/v1/contracts/products/` (Product-First flow) OR `/api/v1/contracts/` (plain) | Yes — returns `workflow_instance_id` (Product-First) or sync (plain) |
| 2 | Wait for contract job to complete | GET (poll) | `/api/v1/jobs/{job_id}/` | n/a |
| 3 | Initiate file upload | POST | `/api/v1/files/init` | No — returns presigned URL |
| 4 | Upload file content to S3 | PUT | (S3 presigned URL) | No |
| 5 | Complete file upload | POST | `/api/v1/files/{file_id}/complete/` | No — SHA-256 + ClamAV |
| 6 | Create asset (data-first) | POST | `/api/v1/assets/data-first/` | Yes — returns `workflow_id` + `asset_id` |
| 7 | Wait for DQ check to complete | GET (poll) | `/api/v1/dq/runs/?asset_id=<id>` | n/a |
| 8 | Wait for compliance scan to complete | GET (poll) | `/api/v1/compliance/runs/?asset_id=<id>` | n/a |
| 9 | Verify asset is ACTIVE | GET | `/api/v1/assets/{asset_id}/` | n/a |

## SDK method coverage (pre-Phase-250.4)

| Step | Required SDK method | Pre-Phase-250.4 status | Pre-Phase-250.4 gap |
| --- | --- | --- | --- |
| 1 | `client.contracts.create_odps(original_raw, extract_odcs=True)` | ✅ exists in [contracts.py](../../sdk/python/datahub_interoperability/contracts.py) (Product-First flow extracts the embedded ODCS automatically) | none |
| 2 | `client.jobs.wait_for(job_id, timeout=300)` | ❌ MISSING | `JobsAPI` had only `get_job` / `cancel_job` / `list_jobs` — no poll helper |
| 3 | `client.files.init_upload(name, content_type, size)` | ✅ exists | none |
| 4 | (raw S3 PUT — out of SDK scope) | n/a | n/a |
| 5 | `client.files.complete_upload(file_id)` | ✅ exists | none |
| 6 | `client.assets.create_data_first(tenant_uuid, file_id, key, name, ...)` | ✅ exists; idempotency-key composer at [idempotency.py](../../sdk/python/datahub_interoperability/idempotency.py) per Phase 250.1.D.5 (auto-composes the `Idempotency-Key` AND sends canonical body bytes) | none |
| 7 | `client.dq.wait_for(asset_id, timeout=180)` | ❌ MISSING | `DQAPI` had only `create_run` / `list_runs` / `get_run` — no poll helper |
| 8 | `client.compliance.wait_for(asset_id, timeout=180)` | ❌ MISSING | `ComplianceAPI` had `poll_async(run_id, ...)` but the DE-1 caller has no run_id; needs an `asset_id`-based variant |
| 9 | `client.assets.get_asset(asset_id)` | ✅ exists | none |

## Phase 250.4 deliverables (this audit's closure)

* **250.4.2**: `JobsAPI.wait_for(job_id, timeout=300)` —
  delivered.
* **250.4.3**: `ComplianceAPI.wait_for(asset_id, timeout=180)`
  — delivered (sibling to existing `poll_async(run_id, ...)`).
* **250.4.4**: `DQAPI.wait_for(asset_id, timeout=180)` —
  delivered.
* **250.4.5**: `tests/integration/test_de1_full_flow.py` —
  full DE-1 sequence against staging in nightly CI.
* **250.4.6**: `.github/workflows/sdk-integration.yml` — nightly
  cron schedule.
* **250.4.7**: `INTERNAL_API_KEY` rotation cadence documented at
  90 days.
* **250.4.8**: SDK already ships matching idempotency-key client
  per Phase 250.1.D.5 (`idempotency.compose_idempotency_key`).
* **250.4.9**: `docs/sdk/programmatic-asset-creation.md` —
  end-to-end programmatic-flow guide with copy-pasteable code.
* **250.4.10**: SLO recorded — DE-1 P95 ≤ 60s on 1 MB payload.

## Path-name spec deviation

The Phase 250 spec consistently references the SDK at
`cli-sdk/meshant_sdk/` — the actual repo layout is
`sdk/python/datahub_interoperability/`. The package was renamed
in Phase ODPS-1 (2026-Q1) but the spec text wasn't updated.
Phase 250.4 deliverables land at the **actual** path; the spec
text drift is documented here for the spec-deviation-tracking
audit.

## Closeout

Phase 250.0.8 (the partial-coverage finding from the original
phase-0 audit) is now CLOSED via this Phase 250.4 deliverable
chain. The SDK has byte-complete coverage of the DE-1 journey
once 250.4.2 / .4.3 / .4.4 land — the integration test in
250.4.5 + the nightly CI in 250.4.6 are the regression-pin.
