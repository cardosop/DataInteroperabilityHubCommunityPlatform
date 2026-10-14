# Pilot Privacy Pack — Week 3 Record

- **Date:** 2026-10-05
- **Change:** `openspec/changes/pilot-readiness` task 3.3
- **Method:** the DPIA/RoPA/DPA runs executed by
  `scripts/verify_privacy_pack.py` against the live API
  (`http://localhost:8001/api/v1`, the seeded shared test stack — real
  HTTP, real rows, real S3 artefact). This record is contract-checked by
  `scripts/check_privacy_pack.py` (GATE-46).
- **Pilot tenant:** slug `pilot-co` (id
  `aaaaaaa1-0001-4001-8001-000000000001`) — recorded decision: the
  dev-estate tenant designated for the pilot rehearsal, provisioned
  idempotently by `hub/apps/tenants/management/commands/
  seed_pilot_privacy_tenant.py` (compliance gates ON, role-separated
  users, one ACTIVE asset with processing purposes + retention). The
  production tenant is provisioned at go-live with the customer's legal
  name.

## DPIA run

The DPIA was run through the real workflow with role separation: the
pilot TENANT_ADMIN created and submitted the record, the pilot **DPO**
reviewed it (`IsDpiaParticipant` / `IsDpiaReviewer` role checks — not the
platform-admin bypass). Wizard payload: processing narrative, risk
narrative, and mitigations; asset-scoped to `pilot-crm` (prepopulation
filled the subject categories, purpose, and jurisdictions).

| Field | Value |
|---|---|
| Record id | dd98f870-cefc-433a-9c48-e5850c4397aa |
| Tenant | pilot-co |
| Title | Pilot CRM DPIA |
| Regime | GDPR |
| Status | APPROVED |
| Risk residual | LOW |
| Reviewer role | DPO |
| Reviewed at | 2026-10-06T00:24:14Z |
| Next review due | 2027-10-06T00:24:14Z (annual) |

Findings: low residual risk — tenant-scoped RLS, encryption at rest and
in transit, role/ABAC governance, and the bounded 3-year retention
policy mitigate the identified risks. The Art 36 consultation branch
(`REQUIRES_CONSULTATION`) is not triggered at LOW residual risk.

## RoPA run

The RoPA was generated against the real pipeline (GDPR, pdf): the
generator walked the pilot tenant's asset + processing purposes +
retention metadata, rendered the Art 30 document, uploaded it to S3,
and served it back through the presigned download URL (the runner
fetched the artefact and verified it is a non-empty PDF).

| Field | Value |
|---|---|
| Generation id | a2d70f68-be9b-4855-a872-8e1c7d50e2ee |
| Regulation | GDPR |
| Output format | pdf |
| Status | COMPLETED |
| Asset count | 1 |
| Gaps | 0 |
| Byte size | 16614 |
| Artifact sha256 | 968f34a820da81be374a6a77977c9b1cdb97e1327d406aaf8425f8bd2db0e353 |
| Completed at | 2026-10-06T00:42:34Z |

**Root cause fixed during the run (regression-pinned):** the documented
`?format=pdf` interface 404'd — DRF's `URL_FORMAT_OVERRIDE` intercepts
the `format` query param in content negotiation and `filter_renderers`
raises a bare `Http404` when no renderer has `format='pdf'` (only
`json` worked, because json doubles as a DRF renderer format). Fixed in
`hub/apps/ropa/views.py` with a `perform_content_negotiation` override
(the audit-export pattern) + two regression pins in
`hub/apps/ropa/tests/test_views.py`; full ropa view suite 11/11.

## Data Processing Agreement

The DPA is registered in the platform's processor-agreement register as
the governance record of the executed addendum. The `document_hash` is
the REAL sha256 of `docs/compliance/dpa-addendum.md` — the record is
cryptographically pinned to the actual legal document (re-verified on
every runner pass and by GATE-46).

| Field | Value |
|---|---|
| Agreement id | e4b474ea-40fc-4de4-8eb4-6b6dbad1a7b4 |
| Processor | Meshant |
| Type | DPA |
| Status | ACTIVE |
| Registration | PILOT-DPA-2026-001 |
| Document hash | 8a4e39d5eeeddfec965b028075d81f990cd419769e55d9ca53a64f8220b6b3d4 |
| Document uri | https://example.com/dpa.pdf |
| Effective from | 2026-10-05 |
| Expires on | 2027-10-07 |
| Sub-processors | AWS (compute + S3), Stripe (billing only), SendGrid (email) |

Notes recorded honestly:

- **document_uri** is the RFC-2606 reserved documentation URI: the
  field is validated by the SSRF guard, which requires a resolvable
  public hostname, and the company domain is not live in DNS yet. The
  CONTENT integrity of the agreement is carried by `document_hash`,
  not the URI; the URI is updated through the same runner when the
  domain goes live.
- **Wet-ink counter-signature is U-gated:** the addendum's sign-off
  section (`docs/compliance/dpa-addendum.md`) is filled at
  counter-signature with the customer's legal entity name and both
  signatures. The platform governance record (ACTIVE) is the machine
  half of "DPA signed"; the legal half requires U + Meshant legal.
- The platform-level PIA (`docs/compliance/privacy-impact-assessment.md`)
  and the DPA addendum both remain the canonical legal documents; this
  pack records the pilot tenant's DPIA/RoPA runs and the agreement
  registration that the plan's 3.3 asks for.

## Exit and deletion (erasure) path

The pilot's exit/deletion path is the platform's erasure machinery,
verified surface-by-surface during this run (no pilot data destroyed —
the destructive end-to-end leg is the Week-4 exit-clause drill, task
4.4):

| Surface | Path |
|---|---|
| Self-service data export | /api/v1/gdpr/export-jobs/export-data/ |
| Self-service erasure | /api/v1/gdpr/erasure-requests/request-erasure/ |
| Admin tenant deletion | /api/v1/admin/tenants/<uuid:tenant_id>/ |
| Tenant file purge | delete_files_for_tenant |
| User file purge | delete_files_for_user |
| Tenant hard-delete sweep | tenant_hard_delete_sweep |

**User level (GDPR Art 17 + 20):** a tenant user exports their data
(`POST /api/v1/gdpr/export-jobs/export-data/` — verified LIVE in this
run: export job `c9887574-2b5f-41af-b697-80f7e9eb8d31` COMPLETED with a
presigned download URL; the archive layout is the documented
`GDPR_EXPORT_FORMAT_VERSION` contract) or requests erasure
(`POST /api/v1/gdpr/erasure-requests/request-erasure/` — executes
immediately: anonymizes the account, revokes sessions and BaaS keys,
anonymizes owned assets, scrubs audit events; retention exception:
`audit_events`). Platform admins can initiate the same per user via the
platform erasure endpoint. File blobs are purged with the
`delete_files_for_user` command (hard purge + audit scrub).

**Tenant level:** the pilot operator soft-deletes the tenant
(`DELETE /api/v1/tenants/{id}/`, or the admin route above) — blocks on
active legal hold (422 `LEGAL_HOLD_ACTIVE`) and open restriction DSAR
(422 `DSAR_RESTRICTION_ACTIVE`); `tenant_hard_delete_sweep` hard-deletes
after the 90-day grace (re-checking legal hold + DSAR at sweep time);
`delete_files_for_tenant` hard-purges every file blob. Operational
steps: `docs/runbooks/tenant-offboarding.md`,
`docs/runbooks/admin-tenant-deactivation.md`,
`docs/SECURITY_AND_COMPLIANCE.md` §GDPR Erasure,
`docs/runbooks/RB-GDPR-001-data-request-failure.md`.

**Verified in this run:** the export leg ran for real; the erasure
route was probed via OPTIONS (it advertises POST) without issuing a
POST; OPTIONS advertises DELETE on both tenant-deletion surfaces; all
three purge commands exist in the checkout. **Incident recorded:** the
first probe design POSTed an empty body to `request-erasure`, which
executes immediately and ignores the body — it really erased the
dev-estate DPO persona (anonymized email, sessions revoked). The
persona was re-provisioned by the idempotent seed command (the durable
recovery path), and the runner now forbids POSTing to that endpoint
(pinned by the contract test). The Week-4 drill exercises the full
delete path against a sacrificial tenant.

## Sign-off

| Party | Role | Status | Date |
|---|---|---|---|
| Meshant | Operator (governance record) | signed — DPIA APPROVED, RoPA COMPLETED, DPA ACTIVE | 2026-10-05 |
| Customer | Controller | U-gated — legal name + wet-ink counter-signature of the DPA addendum | 2026-10-05 |
