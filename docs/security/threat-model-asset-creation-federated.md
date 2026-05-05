# STRIDE Threat Model — Asset Creation (Federated Import) Phase 250.5.E

> **Audience**: Platform security, Engineering leads, DPO, P5 release manager.
> **Phase**: 250.5.E.1 — closes audit gap S-1 / S2-5.
> **Last updated**: 2026-05-04.
> **Status**: Authored as a launch-prerequisite for federated-import GA. **Pre-merge sign-off REQUIRED per 250.5.E.2** (see § Sign-off).

This document captures the threat surface introduced by federated
asset import (Phase 250.5.A) and the surrounding gates (visibility
deprecation 250.3.B, schema-drift detection 250.2.B, IDOR hardening
250.5.C, SSRF guard 250.5.B). Federated import is the first
asset-creation flow on Meshant where one tenant can SURFACE another
tenant's data through Hub APIs — so the cross-tenant + data-residency
+ source-tenant-deletion surfaces deserve explicit treatment beyond
the existing per-feature controls.

The model deliberately follows the format of the prior STRIDE docs
in this directory (e.g. [federation-cross-tenant.md](threat-models/federation-cross-tenant.md))
so security reviewers can compare row-for-row against established
patterns. Every threat row carries a **Pinned by** column referencing
either a test, a code path, or an explicit out-of-scope rationale —
mitigations without an audit trail are aspirational, not load-bearing.

---

## System under threat

| Component | Description |
| --------- | ----------- |
| **Endpoint** | `POST /api/v1/assets/data-first/` (data-first asset creation), `POST /api/v1/assets/` (canonical create), `GET /api/v1/assets/{id}/external-resources/` (list), `POST /api/v1/assets/{id}/external-resources/download/` (single), `POST /api/v1/assets/{id}/external-resources/batch-download/` (batch), `PATCH /api/v1/assets/{id}/` (update), the marketplace_sync orchestration workflow's federated-asset task, and the per-tenant connection CRUD endpoint |
| **Code path** | `MarketplaceIntegrationService.create_federated_asset_with_contracts` → `_enforce_federated_import_gates` (250.5.A) → `Asset.objects.create(source_type=FEDERATED)` → `ExternalResourceReference.objects.get_or_create` (carries `source_tenant_id`) → optional `download_external_resource` (creates File + Dataset rows). For the inbound API: `AssetViewSet.create / data_first / list_external_resources / download_external_resource / batch_download_external_resources`, gated by `TenantScopingMiddleware` (X-Tenant-Id resolution + UUID format guard) and per-action role checks |
| **Data** | `Asset` rows (with `source_type=FEDERATED` + `source_metadata` JSON), `ExternalResourceReference` rows (carry `source_tenant_id` + `source_tenant_deleted_at`), `MarketplaceConnection` rows (per-tenant connector config), downstream `File` + `Dataset` rows created on download, audit events for every gate decision |
| **Capability flag** | `Tenant.federated_import_enabled` (per-tenant opt-in, default FALSE per D250.3 — Phase 250.5.A.2). `Tenant.data_residency_region` (per-tenant region pin — Phase 228 X, reused for the cross-region consent gate). `cross_region_consent` kwarg on the service entry (per-call override per I2-3) |
| **Trust boundaries** | (a) tenant-user browser ↔ Hub API; (b) Hub API ↔ marketplace connector ↔ external marketplace (CKAN, AWS Data Exchange, Snowflake DM, etc.) — the **load-bearing outbound boundary**; (c) consumer tenant A's federated-import flow ↔ source tenant B's data (when Hub-to-Hub federation is wired); (d) `MarketplaceConnection.config` JSON ↔ per-tenant secrets (encrypted at rest); (e) federated `Asset` rows ↔ AUDITOR vs DATA_PROVIDER role surfaces |

---

## STRIDE analysis

### S — Spoofing identity

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| S1 | A user from tenant B reads (or downloads) a federated `ExternalResourceReference` belonging to tenant A by guessing the asset UUID | The `AssetViewSet.get_queryset()` filter is tenant-scoped (`filter(tenant_id=request.tenant_id)`), so cross-tenant `get_object()` lookups hit an empty queryset → DRF's `get_object_or_404` → HTTP 404. The 404 (NOT 403) preserves zero-knowledge of cross-tenant data. | `hub/apps/integrations/tests/security/test_idor.py::CrossTenantExternalResourceListReadProtectionTest` (2 tests covering GET list + POST download cross-tenant) |
| S2 | A non-`DATA_PROVIDER` / non-`TENANT_ADMIN` user triggers an external-resource download (creating File + Dataset rows on the consumer's behalf) | The download + batch-download endpoints carry an explicit role gate at `hub/apps/assets/views.py` — `has_role("DATA_PROVIDER", "TENANT_ADMIN") OR is_platform_admin`, refusing AUDITOR with 403 BEFORE any S3 / persistence work | `test_idor.py::AuditorMutationDenyTest` (3 tests including the side-effect-free assertion: `File.objects.count()` + `Dataset.objects.count()` unchanged after refused call) |
| S3 | A user spoofs the X-Tenant-Id header to act on behalf of another tenant they don't belong to | `TenantScopingMiddleware` (a) validates the X-Tenant-Id is a well-formed UUID (else 400), (b) refuses the request when `request.user` has no membership in the requested tenant via `UserTenantMembershipService.validate_membership` (else 403), (c) falls through to `Tenant.objects.get` with a defence-in-depth `(ValidationError, ValueError)` catcher | `test_idor.py::TenantResolutionFailureModesTest::test_unknown_xtenantid_returns_403` + the membership-check unit tests in `users/tests/test_user_tenant_membership_service.py` |
| S4 | A federated-import call spoofs the `source_metadata.source_tenant_id` to make a tombstone cascade target a different tenant's resources | The cascade signal at `hub/apps/tenants/signals.py::tombstone_federated_resources_on_tenant_delete` only fires for ExternalResourceReference rows whose `source_tenant_id` equals the **deleted** tenant's id. A consumer-side row carrying a fake source_tenant_id is harmless (no cascade fires unless THAT tenant is itself soft-deleted, which requires platform-admin authority). The forged source_tenant_id is also captured in audit metadata so a subsequent operator can identify and clean up the bad row | Source-tenant deletion test in `hub/apps/integrations/tests/test_federated_import_gates.py::SourceTenantDeletionTombstoneTest` |

### T — Tampering with data

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| T1 | A user PATCHes a federated asset's `visibility` field to bypass the deprecation gate | Phase 250.3.B: `visibility` is a derived `@property` from `status`; PATCH writes to the field route through the deprecation setter which (a) issues `DeprecationWarning`, (b) emits `ASSET_VISIBILITY_WRITE_DEPRECATED` audit, (c) is a no-op (the persisted state doesn't change). To make an asset publicly visible the user MUST set `status=PUBLIC`, which goes through the existing visibility-change validation in `business_rules.py::_validate_visibility_change` | `hub/apps/assets/tests/test_visibility_deprecation.py::PatchEndpointIgnoresVisibilityTest` |
| T2 | A user mutates a federated asset's `source_metadata` to redirect the connector to an attacker-controlled marketplace | `source_metadata` is set by the federated-import service code path only; the API-side `AssetUpdateSerializer` doesn't expose it. Direct ORM tampering by a privileged operator is out of scope for the application threat model (mitigated by Phase 234 audit-tamper-evidence when shipped) | DRF serializer field list — `source_metadata` is NOT in `AssetSerializer.Meta.fields` for input |
| T3 | An external marketplace returns a malicious payload that pollutes the consumer's downstream Dataset / File rows | The download path validates Content-Length against `DATA_FIRST_MAX_BODY_BYTES` (100 MB) and runs the standard schema inference + DQ pipeline on the downloaded bytes. SSRF guard (Phase 250.5.B) blocks loopback/RFC1918 destinations at the URL layer. Compliance scan runs on payload metadata for METADATA_ONLY (Phase 250.5.A.3 contract) | `hub/apps/webhooks/ssrf_guard.py::validate_webhook_url` test coverage + body-size cap test |
| T4 | A federated `ExternalResourceReference.source_tenant_deleted_at` is forged to falsely tombstone a row inside the grace window | Only the Tenant soft-delete signal mutates this field (cascade is the only writer). The model field is not exposed on any API surface. Direct ORM writes are out of scope | Code review of `ExternalResourceReference` field surface — no DRF field declaration |
| T5 | An attacker submits a federated import with a spoofed marketplace_type to bypass per-marketplace allowlists | The marketplace_type is enumerated against `MarketplaceType.choices` at serializer + model `clean()` time; unknown values are rejected with structured 400. The connector-factory dispatch at `MarketplaceConnectorFactory` keys on the validated enum value | `MarketplaceConnection.clean` test coverage + factory unit tests |

### R — Repudiation

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| R1 | A consumer tenant claims they never imported a specific external resource, but the source can prove the GET happened | Every `create_federated_asset_with_contracts` call results in (a) Asset row creation (audit-traceable via `created_at` + `created_by`), (b) per-resource `ExternalResourceReference` row, (c) audit events for every gate decision (`FEDERATED_IMPORT_REJECTED`, `FEDERATED_IMPORT_CROSS_REGION_BLOCKED`), (d) `ASSET_CREATED` audit row from the canonical pipeline | `hub/apps/integrations/tests/test_federated_import_gates.py::FederatedImportGateOnTenantFlagTest` (audit row emission on rejection) |
| R2 | A federated import is rejected at the gate but the operator denies the request was made | Both rejection paths (tenant flag + cross-region consent) emit `FEDERATED_IMPORT_REJECTED` audit rows BEFORE raising the typed exception, so the audit row is durable even if the caller swallows the exception | Phase 250.5.A.3 audit-emission code path + tests |
| R3 | A source-tenant deletion cascade fires but the consumer has no record of the event (claims they don't know the source went away) | Per-row `FEDERATED_SOURCE_TENANT_DELETED` audit emission with `details_json` carrying `source_tenant_id`, `consumer_tenant_id`, `external_resource_reference_id`, `asset_id`, `source_tenant_deleted_at`, and `grace_window_expires_at` | `test_federated_import_gates.py::SourceTenantDeletionTombstoneTest::test_soft_delete_populates_tombstone_on_consumer_resources` |
| R4 | An AUDITOR claims they were blocked from a routine compliance check on federated assets | AUDITOR retains READ access to the list endpoint (`test_idor.py::AuditorMutationDenyTest::test_auditor_can_still_list_external_resources`) — only mutate-class actions (download, batch-download) are blocked. The 403 carries an explicit "AUDITOR may LIST but cannot DOWNLOAD" message so the operator-facing rejection is unambiguous | Same test class, plus the explicit error-message convention in views.py |

### I — Information disclosure (load-bearing boundary)

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| I1 | A user from tenant B GETs `/api/v1/assets/{tenant_a_asset_id}/` and learns the asset exists / its name / its key | Cross-tenant `get_object()` returns 404 (not 403) so the API surface does not distinguish "not yours" from "not found". The 404 body MUST NOT carry the asset's name / key / external resource metadata — pinned by `test_idor.py::CrossTenantExternalResourceListReadProtectionTest::test_cross_tenant_list_external_resources_returns_404` (asserts the asset name / key / external resource name strings are NOT in the response body) | Same test |
| I2 | A user submits a malformed X-Tenant-Id and receives a 500 with a Python stack trace, leaking server-side error structure | `TenantScopingMiddleware` validates the UUID format BEFORE the auth + membership checks (Phase 250.5.C.1 audit-pass) and returns a structured 400 (`{"error":"INVALID_TENANT_ID","code":"BAD_REQUEST"}`). The defence-in-depth `(ValidationError, ValueError)` catcher around `Tenant.objects.get` covers any future code path that surfaces the error differently | `test_idor.py::TenantResolutionFailureModesTest::test_malformed_xtenantid_header_returns_400` (asserts response body does NOT contain `"Traceback"` or `"ValidationError"` literals) |
| I3 | An attacker probes without credentials and varies the X-Tenant-Id format to distinguish "401 = malformed tenant" from "401 = bad creds" via header timing | Phase 250.5.C.1 audit-pass: UUID format validation runs BEFORE the auth check, so unauthenticated requests with malformed UUIDs return 400 (NOT 401). Both unauthenticated cases (valid + invalid UUID) now have indistinguishable timing budgets — the validation is constant-time on the UUID parse, not a database round-trip | Same test class + the inline rationale comment at `hub/apps/auth/middleware.py:170-198` |
| I4 | A federated import surfaces the source tenant's data to a consumer tenant in a different region without explicit consent (regulatory cross-region transfer violation) | Phase 250.5.A.6: when `consumer_tenant.data_residency_region != source_tenant.data_residency_region` AND `cross_region_consent=False`, the gate refuses with `FederatedImportRejected("CROSS_REGION_CONSENT_REQUIRED")`. Both `FEDERATED_IMPORT_CROSS_REGION_BLOCKED` AND `FEDERATED_IMPORT_REJECTED` audit rows fire on refusal. NULL on either side ⇒ "unrestricted" (matches Phase 228-X lineage gate posture) | `test_federated_import_gates.py::CrossRegionFederatedImportConsentTest` (2 tests covering both refusal AND consent-acknowledged paths) |
| I5 | A federated `ExternalResourceReference.url` points to an internal cluster service (e.g. `http://kube-state-metrics.kube-system:8080/`), and a download leaks cluster-internal data | Phase 250.5.B `SSRFGuard.validate(url)` rejects loopback / link-local / RFC1918 / cloud-IMDS / non-http(s) schemes BEFORE the connector dispatches the GET. Helm `allow-marketplace-egress` NetworkPolicy excludes the same CIDR ranges at the cluster-network layer (defence in depth) | `hub/apps/integrations/tests/security/test_ssrf.py` (14-vector live-rejection smoke from Phase 250.5.B — loopback / link-local / RFC1918 / IMDS / non-http schemes) + Helm template review |
| I6 | A consumer-tenant operator queries the audit log and learns a source tenant's id (which they shouldn't know about) | Audit rows for cross-tenant federation events scope `tenant=consumer_tenant` on the FK column; the source_tenant_id appears only in `details_json`. Audit-replay queries that JOIN on `audit.tenant_id = consumer_tenants.id` see only the consumer's events — they don't surface the source's audit history | Audit-event tenant FK convention; verified by code review of `create_audit_event` call sites |

### D — Denial of service

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| D1 | An attacker floods POST `/api/v1/assets/data-first/` with large payloads to exhaust connection / memory | `DATA_FIRST_MAX_BODY_BYTES = 100 * 1024 * 1024` (100 MB) hard cap defined at `hub/apps/assets/views.py:392` and enforced at `:449-494` (Content-Length / chunked-transfer / size guard inside the `data_first` action body, BEFORE serializer parsing). Chunked transfer-encoding is rejected with HTTP 411 (chunked uploads can't be capped without buffering, defeating the cap). Per-user 60/min + per-tenant 600/min throttles via `AssetDataFirstUserThrottle` + `AssetDataFirstTenantThrottle` | Existing data-first body-size + throttle tests |
| D2 | An attacker triggers a flood of failed federated-import attempts (each fires the gate + emits an audit row, churning audit-DB writes) | The gate is pre-persistence (no `Asset` row, no Dataset row), so the cost is one Tenant lookup + one audit write per attempt. The audit emission is wrapped in `try/except` so a saturated audit DB doesn't block the rejection — the typed exception still raises. Per-user / per-tenant throttles cap attempts | Throttle classes; audit best-effort wrapper |
| D3 | An attacker triggers slow downloads via partner endpoints that hold connections open indefinitely | Connector HTTP clients use a hard timeout (default 30s); the per-resource download endpoint is not wrapped in `transaction.atomic` so long-running downloads don't hold DB locks. `statement_timeout` clamps any DB query the download path runs | Connector code review + `views.py::download_external_resource` docstring |
| D4 | A misconfigured cascade signal scans every `ExternalResourceReference` row on every Tenant save, slowing down unrelated tenant operations | Cascade signal at `tenants/signals.py::tombstone_federated_resources_on_tenant_delete` short-circuits when (a) `instance.status != DELETED` (no-op for non-deletion saves), (b) the previous status was already DELETED (no-op for re-saves on already-deleted tenants). Filtered ORM update uses the `(source_tenant_id)` index added in migration 0014 | Signal early-exit logic + migration index |
| D5 | A federated-import call triggers a long-running compliance + DQ pipeline that holds workers (DOWNLOAD_ALL strategy on a 50-resource asset) | Per-asset timeout on the orchestration workflow (existing `DEFAULT_STEP_TIMEOUT_SECONDS`); per-resource size cap via `DATA_FIRST_MAX_BODY_BYTES`; sync_job_id audit linkage so per-job watchdog can kill stuck jobs | Existing workflow + watchdog infrastructure |

### E — Elevation of privilege

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| E1 | An AUDITOR triggers an external-resource download (creating File + Dataset rows on the consumer's behalf), gaining write capability they don't formally hold | Phase 250.5.C.1: the role gate at the download + batch-download endpoints requires `DATA_PROVIDER` / `TENANT_ADMIN` / `is_platform_admin`. AUDITOR is refused with 403 BEFORE any persistence work | `test_idor.py::AuditorMutationDenyTest` (3 tests) |
| E2 | A user submits a federated import for a tenant they don't belong to (by spoofing kwargs to the service) | Service entry validates `effective_tenant_id` against `Tenant.all_objects.get(id=...)` (Phase 250.5.A.3 gate), then the downstream `Asset.objects.create(tenant=tenant_obj, ...)` constructor enforces the FK — a forged tenant_id either doesn't exist (404) or doesn't match the request's user (403 via membership check upstream) | Service-layer gate + middleware membership check |
| E3 | A user bypasses the per-tenant `federated_import_enabled=False` flag by calling the orchestration workflow directly | The orchestration workflow's `marketplace_sync.py::create_federated_assets_task` invokes `MarketplaceIntegrationService.create_federated_asset_with_contracts`, which fires the same gate. There's no second entry point that bypasses the gate | Code review of all `create_federated_asset_with_contracts` call sites |
| E4 | An attacker provides a malicious `source_tenant_id` in the asset_mapping to make the cascade signal grant write access to consumer rows | The cascade signal only WRITES `source_tenant_deleted_at` (a single timestamp column); it cannot grant any role / capability / data. The forged `source_tenant_id` would only matter if THAT specific tenant is later soft-deleted — and then the attack reduces to "rows that should NOT have been tombstoned were tombstoned", which the audit log captures and an operator can repair | Cascade signal write surface (1 column) + audit visibility |
| E5 | A platform admin escalates by editing `Tenant.federated_import_enabled` directly | Platform-admin actions are audited via the standard tenant-edit audit trail (`TENANT_UPDATED`). Per the threat-model assumption hierarchy, platform admins are TRUSTED (not adversaries) — separate Phase 234 audit-tamper-evidence work covers the case of a compromised platform-admin account | Out of scope for application threat model; covered by ops + Phase 234 |

---

## Residual risks

| # | Risk | Owner | Tracking |
| - | ---- | ----- | -------- |
| RR1 | Hub-to-Hub federation between same-region tenants without `cross_region_consent=True` is allowed without per-call consent (the consent gate only fires on REGION mismatch). A consumer tenant can pull data from any same-region source without the source's per-call sign-off. | Federation team | Out of scope for 250.5.E (the spec scopes consent to cross-region only). Tracked as P5+ follow-up if customer feedback requires same-region per-call consent. |
| RR2 | The `MarketplaceConnection.config` JSON is documented as "encrypted at rest" but the encryption discipline is not pinned by an automated test (the per-row encryption is library-level via the `encryption.py` module). | Platform security | Phase 250.5.E pen-test scope item (see [pen-test-scope-p5.md](pen-test-scope-p5.md)) |
| RR3 | Source-tenant deletion cascade is best-effort (audit emission wrapped in try/except). A simultaneous outage of audit DB AND tenant DB could leave the cascade column updated but no audit trail. | Platform security + observability | Existing best-effort pattern (matches Phase 250.2.B schema-drift audit). Operator dashboards alert on audit emission failure rate. |

---

## Sign-off

**Required reviewers** (per Meshant security-doc convention, mirrors `threat-models/federation-cross-tenant.md`):

1. Platform security lead
2. Engineering lead — Asset/Federation domain
3. DPO (Data Protection Officer)
4. P5 release manager

**Status: PENDING** — pre-merge sign-off REQUIRED per Phase 250.5.E.2. The merge-gating CI check at `hub/tests/test_security_docs_phase_250_5_e.py::TestThreatModelStructure::test_threat_model_has_sign_off_section` enforces presence of this section; the human sign-off step replaces "PENDING" with a dated entry below.

| Reviewer (role) | Date | Decision | Notes |
| --------------- | ---- | -------- | ----- |
| Platform security | _PENDING_ | _PENDING_ | _PENDING_ |
| Engineering — Asset/Federation | _PENDING_ | _PENDING_ | _PENDING_ |
| DPO | _PENDING_ | _PENDING_ | _PENDING_ |
| P5 release manager | _PENDING_ | _PENDING_ | _PENDING_ |

**Sign-off process** (250.5.E.2 contract):

1. PR author opens a PR including a link to this document and the corresponding pen-test scope (250.5.E.3).
2. Each required reviewer reviews the document, runs the structural test (`pytest hub/tests/test_security_docs_phase_250_5_e.py -v`), and either:
   - Approves → updates the table above with their dated entry + APPROVED decision.
   - Requests changes → comments on the PR; PR author addresses + re-requests review.
3. The PR cannot be merged until ALL four reviewers have entered an APPROVED decision.
4. Merge-gating is enforced procedurally (PR template checklist + reviewer assignment) AND by the structural test (which verifies the section exists, not the sign-off content — the human review is the load-bearing check).

**Why a separate doc-side log instead of relying on GitHub PR approvals**: PR approvals are ephemeral (lost when the PR is squashed-merged or the reviewer's GitHub account churns). The doc-side log is durable in the repo, auditable by future regulators / customers, and survives any GitHub-side history changes.
