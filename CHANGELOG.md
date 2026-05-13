# Changelog

All notable changes to the Meshant Data Interoperability Hub are
documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added — Phase 274: Business Rules Hardening (2026-05-12)

- **BR1 — Marketplace compliance threshold gate.** Listing publication now
  requires a successful ComplianceRun whose risk_level does not exceed the
  tenant's compliance_risk_threshold. Blocked publishes return HTTP 422
  with `COMPLIANCE_THRESHOLD_EXCEEDED`. PLATFORM_ADMIN can bypass with
  `?force_publish=true`. Gated per-tenant behind
  `marketplace_publish_compliance_gate_enabled` (default false for
  existing tenants).
- **BR3 — Semantic tenant flag enforcement.** SPARQL, dereference,
  inference, and export endpoints now return HTTP 403 with
  `SEMANTIC_FEATURE_DISABLED` when the required per-tenant feature flag
  is off. 5 new error codes mapped to tenant action flags.
- **BR4 — AssetActivationRule.** Three-state compliance-aware activation:
  `COMPLIANCE_SCAN_PENDING` (HTTP 409 + `Retry-After: 30`),
  `COMPLIANCE_SCAN_FAILED` (HTTP 422), `COMPLIANCE_NOT_ALLOWED_TO_STORE`
  (HTTP 422). Frontend auto-polls every 30s during pending state.
- **BR13 — RuleChain primitive.** 5 named chains registered for contract
  publish, asset activate, marketplace listing publish, governance
  approval advance, and semantic query execute. Chain runner enforces
  transaction safety and short-circuits on first failure.
- **BR21 — 28 rule classes conformance-backfilled.** All rule classes
  now carry `description`, `tags`, and `openspec_ref` metadata.
- **Infrastructure — CI guardrails.** Catalog conformance CI check
  (`scripts/lint_business_rules_catalog.py`) validates metadata on all
  `@register_rule` classes. Semgrep rule (`.semgrep/business-rules-
  direct-instantiation.yml`) flags direct `BusinessRules(...)` calls
  when a `RuleChain` exists. `/health/business-rules/` endpoint exposes
  degraded-rule registration for SRE alerting.

### Added — Phase 275: Live Data Connectivity (2026-05-12)

- **WarehouseConnection model.** Per-tenant credential vault with KMS+Fernet
  encryption. Supports Snowflake (PAT/JWT/keypair), BigQuery (service-account
  JSON/Workload Identity), Databricks (PAT/OAuth), and Athena (IAM/SigV4).
  Includes SSRF guard at config-save, cascading deletion protection, and
  WarehouseConnectionACL for per-connection RBAC.
- **WarehouseConnector ABC.** 4 connector implementations with parameterised
  binding (never string-concatenated), circuit-breaker integration,
  per-tenant cost guard, and PII-safe logging.
- **Records API.** `GET /api/v1/datasets/{id}/rows/` serves dataset rows as
  JSON (decimals as strings per RFC 7159) or Apache Arrow IPC stream.
  Cursor-based pagination. Routes to file-backed or LIVE_QUERY warehouse
  connector.
- **Delta Sharing.** `GET /api/v1/datasets/{id}/share/` serves the Delta
  Sharing 1.0 protocol with Hub auth + audit injection.
- **dlt WriteAdapter.** Outbound exports to Snowflake/BigQuery/Databricks/
  Athena tables via dlt (schema management, idempotency, normalisation).
  4 new DestinationType values on ScheduledExport.
- **17 audit codes** registered (WAREHOUSE_QUERY_EXECUTED through
  WAREHOUSE_CACHE_REFRESHED). 8 webhook event types. 4 JobType entries.
  Per-warehouse type mapping registry with LossyConversionPolicy.
- **Observability.** 8 Prometheus metrics, 7 alert rules, capacity sizing
  doc, DR/RTO/RPO runbook, credential rotation guide, threat model.

### Added — Phase 277: Whole-Application Audit & Remediation (2026-05-13)

> Phase 277 is a comprehensive cross-cutting audit and remediation sweep
> covering 26 audit dimensions (277.A.1–277.A.26), 100+ P0–P3 remediation
> items, and 9 cross-feature integration closeout tasks.

**Security & AuthZ:**
- RLS policies for 30 tenant-scoped tables across 25 apps (`277.B.018a`)
- `ManagementCommandAdminRouter` BYPASSRLS audit trail (`277.B.084`)
- `tenant_context()` CI enforcement lint (`277.B.095`)
- ABAC enforcement on admin endpoints (`277.B.092`)
- Password complexity + common-password deny-list + HIBP validator (`277.B.065`)
- Account lockout with progressive backoff (`277.B.066`)
- Cross-tab auth token sync via `storage` event (`277.B.067`)
- `/auth/sessions/` endpoint with `end_all_other_sessions` (`277.B.068`)
- Two-person rule for sensitive feature flags (`277.B.096`)
- Data residency cross-validation for warehouse connections (`277.B.093`)
- `UserTenantMembership` unique constraint (`277.B.094`)

**Observability & Monitoring:**
- `asset_operations_total` counter with per-tenant labels (`277.B.051`)
- RQ queue depth Prometheus gauge (`277.B.071`)
- Worker p99 latency histogram + uptime gauge per queue (`277.B.075`)
- RQ task circuit breaker decorator (`277.B.072`)
- Distributed lock consistency for sweeps (`277.B.074`)
- Breach notification SLA gauge with 48h/60h alerts (`277.B.088`)
- Webhook DLQ growth alert + investigation runbook (`277.B.099`)
- `trace_id` on `AuditEvent` for cross-system correlation (`277.B.111`)
- Merkle integrity tamper-detection CI test (`277.B.112`)
- DORA lead-time tracking instrumentation (`277.B.116`)
- Rate-limit headers (`RateLimit-Limit/Remaining/Reset`) (`277.B.101`)

**API & Platform:**
- CPO billing cost overview dashboard (`277.B.031`)
- Records API `StandardCursorPagination` migration (`277.B.048`)
- SDK release automation CI pipeline (`277.B.103`)
- OpenAPI completeness gate (`277.B.081`)
- OpenAPI YAML generation in CI (`277.B.062`)
- API v2 plan + Sunset/Link header coverage (`277.B.082`)
- `GET /tenants/me/usage/` dynamic `RESOURCE_COUNTERS` (`277.B.106`)
- Per-tenant rate limit configuration admin endpoint (`277.B.070`)

**Compliance & Legal:**
- GDPR export/erasure self-service FE UI (`277.B.085`)
- RoPA PDF rendering with full GDPR Art. 30 compliance (`277.B.089`)
- Breach notification SLA alert (`277.B.088`)
- Email accessibility — alt text + plain-text alternative (`277.B.098`)

**Documentation & Ops:**
- CLI reference for 8 missing command groups (`277.B.059`)
- `SECURITY_AND_COMPLIANCE.md` Phase 274+275 refresh (`277.B.064`)
- GraphQL consolidation ADR selecting Strawberry (`277.B.102`)
- CODEOWNERS file with primary+secondary owners (`277.B.109`)
- `INCIDENT_RESPONSE.md` — comprehensive incident playbook (`277.B.056`)
- Postmortem template + process document (`277.B.115`)
- Webhook signing-key rotation drill management command (`277.B.080`)
- ClamAV health probe — Helm exec probes + backend health check (`277.B.079`)
- CI workflow audit — 6 dormant workflows flagged (`277.B.091`)

**Frontend:**
- `<PlanLimitErrorBanner>` shared component with upgrade CTA (`277.B.108`)
- Tenant settings severity coloring + upgrade CTA (`277.B.114`)

**Code Health:**
- All `# type: ignore` markers documented with error codes + reasons (`277.B.038`)
- `datetime.now()` → `timezone.now()` sweep + DTZ lint rule (`277.B.026`, `277.B.076`)
- `makemigrations --check --dry-run` extended to all apps (`277.B.105`)
- RLS linter FK detection extended + test coverage (`277.B.053`)

### Added — Phase 270: Marketplace, tax, compliance & worker-discipline deltas (270.0–270.F)

> Phase 270 closes the OpenSpec `preprod01` change for the
> `marketplace-tax-compliance-deltas` capability — 16 ADDED Requirements
> covering pre-prod-blocker work that surfaced from the gap analysis on
> 2026-03-17. Each sub-phase ships behind its own feature flag and the
> implementation order (`270.0 → 270.A → 270.F → 270.B → 270.C → 270.D →
> 270.E`) was chosen so worker-discipline (270.F) is in place before any
> downstream feature is enabled in staging/prod. See
> `openspec/changes/preprod01/specs/marketplace-tax-compliance-deltas/spec.md`
> for the requirement-level contracts.

**270.A — Marketplace blockers**

- Refund endpoint (`POST /api/v1/marketplace/orders/{id}/refund/`) with full/partial semantics: full refund revokes entitlement, partial preserves; Stripe `idempotency_key` derived from `(order_id, amount_cents)`; webhook dedup via `StripeWebhookEvent`. Audit: `ENTITLEMENT_REVOKED`, `REFUND_PROCESSED`.
- Atomic entitlement creation via Postgres unique partial index `unique_active_entitlement_per_listing_buyer` — concurrent buys produce exactly one `ACTIVE` row.
- Cross-tenant `FREE_AUTO_APPROVE` listing buys create an `AccessRequest` row (status `AUTO_APPROVED`) so the audit trail survives even on the "auto" path.
- Plan-limit enforcement: `marketplace_orders_this_month` counter on `TenantPlanLimits`; rejects with HTTP 402 `PLAN_LIMIT_EXCEEDED` on overflow.

**270.B — Drift detection + AccessRequest SLA**

- `Listing.contract` FK + drift detection: a `LISTING_CONTRACT_DRIFT_DETECTED` event fires when a published listing's contract is mutated; SPA renders a banner; re-publishing clears the drift flag.
- `revoke_expired_access` runs as a daily K8s `CronJob` (replaces the prior signal-based path); iterates tenants under `tenant_context()` so RLS is respected; PENDING-too-long entries roll to EXPIRED with the SLA timestamp captured.

**270.C — Compliance authorisation, license & strict-mode**

- **270.C.1** Tenant-scoped async job IDs: `POST /scan-file-async` now returns `<sha256(X-Actor-Id)[:8]>_<uuid>`; cross-tenant polls return HTTP 403 `JOB_TENANT_MISMATCH`. Constant-time prefix comparison via `hmac.compare_digest`. Legacy UUID-only ids accepted with no actor check during the rollout window; they age out of Redis after the 1h/24h TTLs.
- **270.C.2** Compliance microservice tenant authorisation: every authenticated request is cross-checked at three FastAPI endpoints (`/scan-file`, `/scan-dataframe`, `/scan-file-async`) — body `tenant_id` vs `X-Actor-Id` header. Decision: agree → use; disagree → 400 `TENANT_MISMATCH`; only header → use it; only body in production → 400 `MISSING_X_ACTOR_ID` (warn-only in dev/staging during the migration window); neither → 400 `TENANT_REQUIRED`. `InternalApiKeyMiddleware` normalises and stashes `X-Actor-Id` on `request.state.actor_id`. `ComplianceServiceClient(tenant_id=...)` constructor parameter binds a client to a tenant; the legacy service-level `"hub"` actor identifier is removed — `X-Actor-Id` is now always the tenant UUID. Worker (`poll_compliance_job`) + service-bound (`TrainingDataValidationService`) callers upgraded to pass tenant_id explicitly.
- **270.C.3** `INTERNAL_API_KEY` 90-day rotation cadence via AWS Secrets Manager rotation Lambda; ExternalSecrets Operator syncs `current` + `previous` into K8s Secrets; `InternalApiKeyMiddleware` accepts both keys during the 24h overlap window. `KeyRotationOverdue` Prometheus alert at 95 days.
- **270.C.4** Per-tenant compliance legal-basis strict mode: `tenant.compliance_legal_basis_strict` opt-in flag forwards as `X-Compliance-Legal-Basis-Strict: true`; strict mode raises `LegalBasisInvalidError` → HTTP 422; lenient mode preserves the Phase 19.7.1 issue-in-report shape.
- **270.C.5** Tenant license validation: `tenant.licensed_compliance_regulations` array; unlicensed regulations produce a `LICENSE_WARNING` issue (default) or HTTP 422 in strict mode. License warnings merge with (not overwrite) `compliance_run.metadata_json` so they survive a subsequent async-result persist.

**270.D — Stripe Tax**

- Stripe Tax enabled on `PaymentIntent` / `Subscription` via `automatic_tax={"enabled": True}`. Reverse-charges B2B transactions when the customer has a verified VAT ID. `TaxRegistrationOverdue` alert fires when a tax-registration threshold is breached.

**270.E — `PaymentTransaction.amount_cents`**

- Dual-write `Decimal amount` + integer `amount_cents` columns; reads prefer `amount_cents`. Backfill migration populates pre-existing rows; the `PaymentTransaction.save()` override keeps the two in sync going forward.

**270.F — Cross-cutting worker discipline (P0 prereq)**

- All marketplace + compliance + billing background tasks now wrap their tenant-scoped DB lookups in `_run_with_tenant_context(tenant_id, …)`; enqueue sites forward `tenant_id` as a kwarg. Affected tasks: `send_marketplace_sync_completion_email`, `send_marketplace_sync_failure_email`, `send_marketplace_connection_test_failure_email`, `poll_compliance_job`, `_reenqueue`, `cleanup_old_webhook_events`, `cleanup_old_usage_records`. Regression tests pin the safety net by binding queries against `current_setting('app.current_tenant_id', true)` directly — without `tenant_context`, the GUC is empty and `DoesNotExist` is raised; with it, the row resolves.

**New environment variables** (services-side):

- `ENVIRONMENT` (`production` / `staging` / `development`) — read by the compliance microservice's tenant-authz cross-check to decide whether "only body tenant_id" returns 400 or just warns. Defaults to `development` for local-dev compatibility.
- `INTERNAL_API_KEY_PREVIOUS` + `INTERNAL_API_KEY_PREVIOUS_EXPIRES_AT` — used by the FastAPI services during the 24h rotation overlap window (Phase 270.C.3).

**New tests** (high-signal, RLS- and behaviour-pinning):

- `services/compliance-service/tests/test_tenant_actor_id_cross_check.py` (270.C.2) — agree / disagree / only-header / only-body-prod-vs-dev / neither across all 3 FastAPI endpoints.
- `services/compliance-service/tests/test_async_job_tenant_scoping.py` (270.C.1) — job-id-prefix sha256 round-trip + cross-tenant 403.
- `hub/apps/compliance/tests/test_poll_compliance_job_tenant_context.py` (270.F.2) — `ComplianceRun` safety-net assertion via `current_setting` direct binding.
- `hub/apps/notifications/tests/test_marketplace_tasks_tenant_context.py` (270.F.1) — `inspect.signature` + source-grep pins for the 3 marketplace notification tasks.

### Added — Phase 235: PLATFORM_ADMIN operations surface (235.0–235.6)

> Phase 235 closes the OpenSpec `preprod01` change for the three
> admin-* capabilities (per-tenant feature flags, tenant lifecycle,
> impersonation): one cross-tenant operator-facing surface that
> covers the customer-success / on-call / compliance flows the
> Phase 232–234 audit + retention work depends on.

**New endpoints (all PLATFORM_ADMIN-only, mounted under `/api/v1/admin/`):**

- `POST /api/v1/admin/tenants/` (Phase 235.2) — provisions a tenant + TENANT_ADMIN invitation in one atomic transaction. Emits `TENANT_CREATED`; the invited admin receives a 7-day-expiring `send_invitation_email`.
- `DELETE /api/v1/admin/tenants/{id}/` (Phase 235.3) — soft-deletes a tenant with a 90-day grace window. Stamps `scheduled_for_deletion_at` + `deleted_at`; emits `TENANT_SOFT_DELETED`. Rejects with 422 + `LEGAL_HOLD_ACTIVE` or `DSAR_RESTRICTION_ACTIVE` on the two blocker conditions; 409 + `ALREADY_DELETED` on idempotent re-clicks. Daily `tenant_hard_delete_sweep` cron then hard-deletes after the grace + re-checks the blockers under a row lock; emits `TENANT_HARD_DELETED` before the cascade (the audit row survives via `AuditEvent.tenant on_delete=SET_NULL`).
- `GET / PUT /api/v1/admin/tenants/{id}/feature-flags/` + `POST /api/v1/admin/feature-flag-approvals/{id}/approve/` (Phase 235.1) — per-tenant feature-flag CRUD with a two-person rule on sensitive flags. Non-sensitive flips land directly (`TENANT_FEATURE_FLAG_CHANGED`); sensitive flips open a `FeatureFlagFlipApproval` row (HTTP 202 + `FEATURE_FLAG_FLIP_APPROVAL_REQUESTED`) that a SECOND PLATFORM_ADMIN must approve (`FEATURE_FLAG_FLIP_APPROVED` + `TENANT_FEATURE_FLAG_CHANGED` in one atomic txn). Self-approval rejected at two layers (model guard + API permission) with `SELF_APPROVAL_FORBIDDEN`. Per-admin rate-limit 60 flips/hour.
- `POST /api/v1/admin/impersonate/` + `POST /api/v1/admin/impersonate/exit/` (Phase 235.4) — opt-in per-tenant impersonation. Returns a short-lived JWT (capped at 240 min) carrying an `impersonation_session_id` claim. Rejection codes (`IMPERSONATION_NOT_ENABLED` / `TARGET_IS_PLATFORM_ADMIN` / `TARGET_INACTIVE`) emit `IMPERSONATION_REJECTED` for forensics. Happy-path emits `IMPERSONATION_STARTED` in BOTH tenants (auditor-facing + security-team-facing), schedules a courtesy email to the impersonated user, and persists the session via `ImpersonationSession` (RLS-paired). Exit accepts either the operator's regular session OR the impersonation JWT itself (the latter via `IsPlatformAdminOrActiveImpersonator` permission + a defence-in-depth `SESSION_ID_MISMATCH` check). Every-5-minute `expire_impersonation_sessions` cron ends ACTIVE sessions past `expires_at` with `end_reason="expired"`.
- `GET /api/v1/admin/dashboard/summary/` (Phase 235.5) — consolidated operator dashboard. Six widget blocks (tenants / webhooks / audit / compliance / billing / governance) via a single `aggregate()` query per table — 12 `COUNT(*) FILTER (WHERE ...)` annotations in 7 round-trips. Cached for 5 minutes; `?refresh=true` bypasses for ops mid-incident. Per-widget error isolation: if ONE aggregator throws, the failing widget returns `{"widget_error": true}` and the other five render normally (the SPA renders an inline `role="alert"` fallback). `Cache-Control: private, max-age=60` for browser-level dedup.

**New audit-event constants** (`hub/apps/audit/event_types.py`):

- `TENANT_CREATED` (235.2), `TENANT_SOFT_DELETED` (235.3), `TENANT_HARD_DELETED` (235.3) — tenant lifecycle.
- `TENANT_FEATURE_FLAG_CHANGED` (235.1), `FEATURE_FLAG_FLIP_APPROVAL_REQUESTED` (235.1), `FEATURE_FLAG_FLIP_APPROVED` (235.1) — feature-flag two-person rule.
- `IMPERSONATION_STARTED` (235.4), `IMPERSONATION_ENDED` (235.4), `IMPERSONATION_REJECTED` (235.4) — impersonation lifecycle. `IMPERSONATION_REJECTED.details_json.code` is the rejection discriminator (`IMPERSONATION_NOT_ENABLED` / `TARGET_IS_PLATFORM_ADMIN` / `TARGET_INACTIVE`).

**New database migrations:**

- `hub/apps/tenants/migrations/0056_feature_flag_flip_approval.py` + `0057_enable_rls_feature_flag_flip_approval.py` — Phase 235.1 model + paired RLS policy.
- `hub/apps/tenants/migrations/0058_tenant_scheduled_for_deletion_and_legal_hold.py` — Phase 235.3 `Tenant.scheduled_for_deletion_at` + `Tenant.legal_hold`.
- `hub/apps/tenants/migrations/0059_phase_235_4_impersonation.py` + `0060_enable_rls_impersonation_session.py` — Phase 235.4 `Tenant.impersonation_allowed` + `Tenant.impersonation_default_max_minutes` + `ImpersonationSession` model + paired RLS policy.

**New Prometheus metrics** (`hub/apps/observability/otel_metrics.py`):

- `admin_dashboard_summary_cache_total{outcome}` (Phase 235.6) — counter labelled by `hit` / `miss`; drives the Grafana cache-hit-ratio panel + the SLO ≥ 0.8 alert.
- `admin_dashboard_summary_aggregate_duration_seconds` (Phase 235.6) — histogram with buckets `0.05 / 0.1 / 0.25 / 0.5 / 1 / 2 / 5 / 10` seconds; drives the P50/P95/P99 latency panel + the P95 > 2s alert.

The pre-existing `audit_events_total{action, resource_type, result}` counter covers every Phase 235 audit-event type via the `action` label — no per-action counter needed.

**New Grafana dashboard:** `monitoring/grafana/dashboards/admin-ops.json` — 7 panels covering tenant lifecycle rate, impersonation lifecycle rate, feature-flag flip rate, 24h cumulative counts, dashboard cache hit-ratio SLO, dashboard P50/P95/P99 latency, admin audit-failure rate by action.

**New runbooks:**

- `docs/runbooks/admin-impersonation.md` (Phase 235.6.4) — operator guide for impersonation.
- `docs/runbooks/admin-feature-flag-flip.md` (Phase 235.6.5) — operator guide for feature-flag flips.
- `docs/runbooks/admin-tenant-deactivation.md` (Phase 235.6.AUDIT.2) — operator guide for the soft-delete + 90-day grace + hard-delete pipeline.

### Added — Phase 234: Audit-trail tamper-evidence + retention + FTS + observability (234.1–234.7)

> Phase 234 closes the OpenSpec `preprod01` change for the audit-events
> capability: hash-chain tamper-evidence + Merkle-snapshot anchoring,
> per-event-type retention overrides, permanent-delete after 90-day
> grace, Postgres FTS over audit details, and the cross-cutting
> observability stack (metrics, dashboard, alerts, runbook).

**New and updated controls:**

- Append-only per-tenant SHA-256 hash chain on `AuditEvent` (Phase 234.1) — `chain_sequence` + `prev_chain_hash` + `chain_hash` are populated by the model's `save()`; the chain is verifiable end-to-end via `GET /api/v1/audit/integrity/verify`. GDPR-erasure gaps are tolerated (informational `gaps` field) per the 234.1 × 232.2 cross-spec.
- Hourly Merkle snapshots (Phase 234.1.5) — `audit_merkle_snapshots` table + S3 Object-Lock proof upload signed with the tenant's rolling key ring; defends against full-chain rewrites that would otherwise present as internally-consistent forgeries.
- Per-event-type retention overrides (Phase 234.5) — new `AuditEventRetentionPolicy` model + RLS-paired migration; `regulation_keys` are resolved via the same Phase 232.7 registry as data-resource retention. CRUD at `/api/v1/audit/event-retention-policies/` (TENANT_ADMIN only) with `AUDIT_EVENT_RETENTION_POLICY_{CREATED,UPDATED,DELETED}` audit emission.
- 90-day permanent-delete sweep after archival (Phase 234.4) — daily Kubernetes CronJob hard-deletes archived rows past the grace window, skipping legal-hold tenants and open DSAR-RESTRICTION resources. One `AUDIT_RETENTION_PURGED` meta-audit per (tenant, run) emitted BEFORE the bulk delete (atomic in one admin-alias transaction so both commit together or both roll back).
- Postgres FTS over audit details (Phase 234.6) — `details_json_tsvector` STORED `GENERATED` column composing weighted lexemes from `action` (weight A), `resource_type` (B), and `details_json` (C via `jsonb_to_tsvector`). Concurrent GIN index `audit_events_details_tsv_gin`. `?q=` query param on `/api/v1/audit/audit-events/` accepts `websearch_to_tsquery` syntax (quoted phrases, `-negation`, `or`). ALWAYS ANDed with tenant scope server-side.
- Cross-cutting observability (Phase 234.7) — four bare-named Prometheus / OTel metrics (`audit_chain_break_total`, `audit_merkle_snapshot_duration_seconds`, `audit_retention_purged_total`, `audit_search_query_duration_seconds`). Three new audit-event constants (`AUDIT_INTEGRITY_VERIFIED`, `AUDIT_INTEGRITY_MISMATCH`, `AUDIT_GDPR_PURGED`). Grafana dashboard `monitoring/grafana/dashboards/audit-health.json` + Prometheus alert rules `monitoring/prometheus/alerts/audit.yml` + on-call runbook `docs/runbooks/audit-tamper-evidence.md` covering the chain-break / merkle-slow / FTS-slow / retention-stalled triage flows.

**New endpoints:**

- `GET /api/v1/audit/audit-events/?q=...` — Postgres FTS path (Phase 234.6).
- `GET /api/v1/audit/integrity/verify/` — chain integrity verifier (Phase 234.1.8; `?include_snapshots=true` cross-checks the Merkle anchors).
- `/api/v1/audit/event-retention-policies/` — TENANT_ADMIN CRUD over per-event-type retention overrides (Phase 234.5).

**New event-type constants** (`hub/apps/audit/event_types.py`):

- `AUDIT_RETENTION_PURGED` (234.4) — meta-audit for permanent-delete sweeps.
- `AUDIT_EVENT_RETENTION_POLICY_{CREATED,UPDATED,DELETED}` (234.5) — CRUD audit for the new retention-override table.
- `AUDIT_INTEGRITY_VERIFIED` / `AUDIT_INTEGRITY_MISMATCH` (234.7.1) — emitted by the verifier endpoint on every run.
- `AUDIT_GDPR_PURGED` (234.7.1) — placeholder for the DSAR-erasure path emission (constant pinned now; emission wired by the DSAR fulfilment subsystem).

**New database migrations:**

- `hub/apps/audit/migrations/0006_add_chain_fields.py` — chain_sequence + prev_chain_hash + chain_hash.
- `hub/apps/audit/migrations/0007_chain_index_concurrent.py` — non-blocking `CREATE INDEX CONCURRENTLY` on (tenant, chain_sequence).
- `hub/apps/audit/migrations/0008_audit_event_retention_policy.py` + `0009_enable_rls_audit_event_retention_policy.py` — new model + paired RLS policy.
- `hub/apps/audit/migrations/0010_audit_event_details_tsvector.py` — STORED `GeneratedField` `details_json_tsvector`.
- `hub/apps/audit/migrations/0011_audit_event_tsvector_index_concurrent.py` — non-blocking GIN index for FTS.

**New runbooks:**

- `docs/runbooks/audit-search-rollout.md` (Phase 234.6.AUDIT.1) — 50M-row threshold + trigger-based contingency.
- `docs/runbooks/audit-tamper-evidence.md` (Phase 234.7.5) — on-call triage for the 5 audit alerts; includes the production smoke-test scenario for `234.DoD.5` (forge audit row via raw SQL → verifier detects mismatch within 1h).

**New management commands:**

- `python hub/manage.py backfill_audit_chain` (Phase 234.1.9) — populate chain fields on pre-Phase 234 rows.
- `python hub/manage.py audit_merkle_snapshot_sweep` (Phase 234.1.5) — hourly tenant-window snapshot pipeline; CronJob entry point.
- `python hub/manage.py audit_permanent_delete_sweep` (Phase 234.4) — daily permanent-delete sweep; `--dry-run` + `--age-days` + `--tenant-id` flags.

**OpenAPI snapshot regeneration:**

```bash
# Run this BEFORE merge to refresh docs/api/openapi-baseline.json:
docker compose -f docker-compose.yml run --rm api \
  python scripts/regenerate-openapi-spec.py
```

The snapshot must be in sync with the additive endpoint changes (`?q=` parameter on the audit-events list + the new event-retention-policies CRUD + the integrity verifier) per `234.DoD.3` (additive only).

### Added — Phase 260: Datasets & Files hardening + auth defence-in-depth (260.A–260.7.J)

> Phase 260 closes the OpenSpec `preprod01` change for the datasets-files
> capability and adds a defence-in-depth layer to the auth surface (cookie-mode,
> DB-backed lockout, logout-all). The phase ships under the
> `openspec/changes/preprod01/specs/datasets-files/` capability with an
> extension to `file-virus-scanning`. Production rollout per
> `260.DoD.3` is staged: staging soak ≥7 days → prod canary 10% → 100%.

**New and updated controls:**

- HTTP-only secure-cookie auth mode (Phase 260.A) — `USE_HTTPONLY_AUTH_COOKIES` defaults to True in prod; cookie carries the access token with `Domain`/`SameSite=Strict`/`Secure`/`HttpOnly` set per the `260-cookie-rollout-production-flip.md` runbook.
- DB-backed lockout (Phase 260.B.4) — failed-login attempts persist across pod restarts; lockout signals via the audit `AUTH_LOCKOUT` event so the on-call sees lockouts even if Redis is unavailable.
- Logout-all SLO contract (Phase 260.B.1, 260.DoD.4) — `POST /api/v1/auth/logout/` with no body revokes every refresh token and increments `authz_version`, invalidating outstanding access JWTs within 1s of the logout response.
- File magic-byte content-type validation (Phase 260.2.B) — `MAGIC_BYTE_VALIDATION_ENABLED` (default True in staging/prod) re-reads the head bytes from S3 at `complete/` and rejects PE-as-CSV / SQL-as-text and other declared/actual MIME mismatches before the file transitions to ACTIVE.
- File-metadata-viewed audit sampling (Phase 260.2.F) — `FILE_METADATA_VIEWED` audit event fires on detail reads behind a sampled flag to keep audit-log volume bounded.
- Files REST surface kill-switch (Phase 260.3.B) — `files_enabled` per-tenant feature flag (default ON) with a registry-level kill-switch in `hub/apps/tenants/feature_flag_registry.py`.
- Lightweight scan-status polling endpoint (Phase 260.3.D) — `GET /api/v1/files/{id}/scan-status/` returns just `scan_status` + `scanned_at` so the FileListPage can poll at 2s without trip­ping the metadata-viewed audit.
- Dataset retire lifecycle (Phase 260.4.A.1) — `POST /api/v1/datasets/{id}/retire/` flips ACTIVE → RETIRED with `select_for_update` row locking and emits `DATASET_RETIRED`.
- Tenant file-storage quota meter (Phase 260.4.G) — `GET /api/v1/files/quota/` returns `used_bytes`, `limit_bytes`, `utilization_pct` for the FileListPage meter.
- Eligible-orphan detection (Phase 260.5) — when the LAST `Dataset` row for `(tenant, file_id)` is deleted from RETIRED/missing/NULL parent contexts, the backing `File` transitions to DELETED inside the same Django transaction; emits `FILE_ORPHAN_DETECTED`.
- File `purge_deleted_files` cron + GDPR hard-delete webhook + audit (Phase 260.7.G) — `WebhookEventType.FILE_PURGED` emitted from BOTH the grace-period cron and the GDPR right-to-erasure path (`hard_purge_file_for_erasure`); per-call best-effort try/except around the publisher so the cron always commits the actual delete.
- Multipart abort + resume contract (Phase 260.7.J) — full-chain pytest at the DRF + real-S3 (MinIO) layer plus a Playwright E2E that drives the browser → API → S3 reconciliation seam through `page.request`. Pins the post-complete `/parts/` typed-code contract (`MULTIPART_UPLOAD_NO_LONGER_EXISTS`).

**New endpoints:**

- `GET /api/v1/files/quota/` — tenant file-storage quota meter (Phase 260.4.G).
- `GET /api/v1/files/{id}/scan-status/` — lightweight scan-status poll (Phase 260.3.D).
- `GET /api/v1/files/{id}/parts/` — multipart upload reconciliation (Phase 260.7.J).
- `POST /api/v1/datasets/{id}/retire/` — explicit retire lifecycle (Phase 260.4.A.1).
- `POST /api/v1/files/{id}/chunks/init/` — per-chunk presigned URL minting for the multipart upload UI (Phase 260.3.E).

**New audit-event codes:**

- `FILE_METADATA_VIEWED` (260.2.F), `FILE_ORPHAN_DETECTED` (260.5), `FILE_PURGED` (260.7.G), `DATASET_RETIRED` (260.4.A.1), `AUTH_LOCKOUT` (260.B.4).

**New webhook events:**

- `WebhookEventType.FILE_PURGED` (Phase 260.7.G) — fires from BOTH the grace-period purge cron AND the GDPR `hard_purge_file_for_erasure` path. Subscribers should run cleanup that wasn't safe during the grace window (cascading deletes in CRM / downstream warehouses, archive-to-cold-storage triggers).

**New runbooks under `docs/runbooks/`:**

- `260-cookie-rollout-production-flip.md` (260.A), `datasets-files-dr.md` (260 ops), `kms-rotation.md` (260.7.H), `openspec-archive-preprod01-phase260.md` (260.DoD.8 archive procedure), `file-virus-scan-incident.md` (260 ops).

**Prometheus alert rules + auto-rollback (260.DoD.4):**

- `monitoring/prometheus/alerts/datasets-files.yml` — error-rate, ClamAV backlog, magic-byte spike, scheduled-ingestion stuck, tenant quota pressure, plus the SLO escalation triplet (`DatasetFilesP95Regressed` 1× SLO warning, `DatasetFilesP95TwoXSLO` 2× page, `DatasetFilesP95ThreeXSLOAutoRollback` 3× critical with `auto_rollback: "true"` label).
- `.github/workflows/auto-rollback-datasets-files.yml` — Alertmanager `repository_dispatch` consumer that runs `helm rollback` on the previous revision; mirrors `auto-rollback-asset-creation.yml` from Phase 250.DoD.4.

**Production smoke tests (260.DoD.4 + 260.DoD.7):**

- `tests/smoke/test_phase260_dod4_post_deploy.py` — logout-all SLO + legitimate tenant probe.
- `tests/smoke/test_phase260_cross_tenant_denial.py` — synthetic cross-tenant request denial counter.
- `tests/smoke/test_phase260_dod7_post_deploy.py` — full datasets-files lifecycle (file upload + virus scan + dataset create/retire + orphan-cleanup), EICAR upload blocks download, magic-byte mismatch rejects PE-as-CSV, quota meter reflects uploaded bytes.

**Stakeholder governance (260.DoD.6):**

- `docs/raci/datasets-files-hardening.md` — RACI matrix across Eng / EM / PM / Sec / Legal / DPO / Support / SRE / DevRel / CS / Pricing for storage lifecycle, ClamAV posture, CORS/Terraform, error-code catalogue, and customer communications.

### Added — Phase 250: Asset-creation hardening (250.1–250.7)

> Phase 250 hardens data-first asset creation and closes the identified
> security/operability gaps: fail-closed persistence, workflow versioning,
> idempotent create semantics, federated-import safety gates, tenant feature
> controls, semantic graceful-degrade, optimistic-locking enforcement, and
> rate-limit controls.

**New and updated controls:**

- Workflow WARN audit event support with `ASSET_WORKFLOW_WARN_LOGGED` emission for non-fatal warning paths in asset-creation workflows.
- Per-user and per-tenant throttling for asset creation surfaces (`create` + `data_first`) to reduce abuse risk while preserving tenant isolation.
- Hardened test-database bootstrap path in `scripts/migrate-test-dbs.sh` to detect/drop invalid PostgreSQL DB states (`datconnlimit=-2`) before clone fallback.
- Asset-creation operational artifacts under `docs/` including runbooks, ADR set, risk register, capacity plan, and RACI matrix for cross-functional execution.
- Prometheus asset-creation alert rules are wired in both development and production Prometheus rule files.

### Added — Phase 230: Semantic platform expansion (REQ-SEM-* sub-phases)

> Phase 230 ships the semantic capability suite: SPARQL inference, bulk
> RDF export, tombstone lifecycle, Memento versioning, contract
> relationships, JSON-LD context alias, OWL inference, SPARQL
> federation with allow-list, Schema.org SEO, custom-ontology
> registration, ontology-aware search, W3C Linked Data Notifications,
> and the GraphQL-LD endpoint.  Every post-MVP sub-phase (230.7–230.13)
> ships behind a per-tenant flag with default OFF; production-tenant
> flip-on requires a separate ops change-request including capacity
> sizing, rollback plan, and post-deploy metric snapshot per Phase 230.DoD.2.

**New endpoints:**

- `POST /api/v1/semantic/export` — bulk RDF export (n-triples / turtle / rdf-xml / ld+json) with the 100M-triple cap and 5/5min throttle (Phase 230.2 / REQ-SEM-EXPORT-001).
- `GET /api/v1/semantic/relationships/<contract_id>` — RDF relationships with content negotiation, tenant-scoped 404 (Phase 230.5 / REQ-SEM-RELATIONSHIPS-001).
- `GET /api/v1/semantic/resource/<type>/<id>/version/<snapshot_at>` + `/timemap` — Memento RFC 7089 versioned dereference + TimeMap (Phase 230.4 / REQ-SEM-MEMENTO-001).
- `GET /api/v1/semantic/context` — extension-less alias for `context.jsonld` (Phase 230.6 / REQ-SEM-CONTEXT-ALIAS-001).
- CRUD `/api/v1/tenants/<id>/sparql-endpoints/` — per-tenant SPARQL federation allow-list, TENANT_ADMIN-only (Phase 230.8 / REQ-SEM-FED-001).
- CRUD `/api/v1/semantic/ontologies/` — per-tenant custom ontology upload + lifecycle (Phase 230.10 / REQ-SEM-ONTO-001).
- `POST /api/v1/semantic/ldn/inbox/<tenant_id>` + listing endpoints — W3C LDN inbox with HTTP-signature verification (Phase 230.12 / REQ-SEM-LDN-001).
- `POST /api/v1/semantic/graphql` — GraphQL-LD endpoint with depth ≤ 5, complexity ≤ 100, 10s timeout, 60 q/min throttle (Phase 230.13 / REQ-SEM-GQL-001).

**Behaviour changes (additive-only per D230.17 — no MODIFIED endpoints):**

- `GET /api/v1/semantic/sparql` now honours `Tenant.semantic_inference_enabled` — when True, queries route to the OWL Mini inferred dataset (Phase 230.7 / REQ-SEM-INFERENCE-001).
- `GET /api/search/?semantic=true` triggers ontology-aware query expansion when `Tenant.semantic_search_enabled=True` (Phase 230.11 / REQ-SEM-SEARCH-EXPAND-001).
- Dereference responses + SPARQL `DESCRIBE` now include `Link: <…/ldn/inbox/{tenant_id}>; rel="…ldp#inbox"` for tenants with LDN enabled (Phase 230.12 / REQ-SEM-LDN-002).
- Public marketplace listing / dataset / asset pages emit Schema.org `<script type="application/ld+json">` (Phase 230.9 / REQ-SEM-SEO-001) — behind-auth pages do NOT emit.
- Resources with `semantic_federate_optout=True` (per-resource opt-out on Asset / Contract / Dataset) are filtered at every cross-boundary surface: `rdf_export`, LDN outbound, SPARQL federation responses (Phase 230.8.9 / REQ-SEM-FED-002).

**New audit-event codes (registered in [hub/apps/audit/models.py](hub/apps/audit/models.py)):**

- `SEMANTIC_EXPORT` (Phase 230.2)
- `SEMANTIC_TOMBSTONE` (Phase 230.3)
- `SEMANTIC_FEDERATED_QUERY`, `SEMANTIC_FEDERATION_ALLOWLIST_ADD`, `SEMANTIC_FEDERATION_ALLOWLIST_REMOVE` (Phase 230.8)
- `SEMANTIC_LDN_INBOUND`, `SEMANTIC_LDN_OUTBOUND`, `SEMANTIC_LDN_SUBSCRIPTION_CREATED`, `SEMANTIC_LDN_SUBSCRIPTION_DELETED` (Phase 230.12)
- `SEMANTIC_GRAPHQL_QUERY` (Phase 230.13)

**New per-tenant flags (all default False):**

- `Tenant.semantic_inference_enabled` (230.7)
- `Tenant.semantic_custom_ontology_enabled` (230.10)
- `Tenant.semantic_search_enabled` (230.11)
- `Tenant.semantic_ldn_enabled` (230.12)
- `Tenant.semantic_graphql_ld_enabled` (230.13)

Phase 230.8 federation gates via empty `TenantSparqlEndpoint` allow-list (no boolean flag — empty list = OFF). Phase 230.9 Schema.org has no per-tenant flag because the gating model is page-visibility (public-page-only emission), which is a stricter privacy contract than a tenant flag.

**New runbooks under `docs/runbooks/`:**

- `semantic-export.md`, `semantic-tombstone.md`, `semantic-memento.md`, `semantic-inference.md`, `semantic-federation.md`, `semantic-ontology.md`, `semantic-ldn.md`, `semantic-graphql.md`.

**Threat models (per Phase 230.DoD.5):**

- `docs/security/threat-models/federation-cross-tenant.md` (Phase 230.8).
- `docs/security/threat-models/ldn-cross-tenant.md` (Phase 230.12).

Both threat models include a "Legal-team sign-off" section that MUST be filled in the merging PR description before the per-tenant flag is flipped True for any production tenant.

**Bundle-size CI gate extension (Phase 230.13.10):**

- [scripts/bundle_size_check.mjs](scripts/bundle_size_check.mjs) gains a layered 5% growth-ratio cap atop the existing 30 KB absolute cap. PRs fail on either trip.

### Added — Phase 240: Data-quality feature hardening (240.0–240.5 sub-phases)

> Phase 240 closes the 28-gap audit on the data-quality feature
> identified pre-MVP: engine-agnostic adapter abstraction, ODPS-aligned
> profile suite, alert-delivery channel parity, structured-logging
> migration, distributed tracing across the hub→dq-service boundary,
> Helm-canonical configuration, payload signing on the internal
> network, PII redaction sweep, and the operational runbook + SLOs.
> Per-tenant rollout follows D240.18: `Tenant.data_quality_enabled`
> defaults TRUE on existing tenants (no surprise disable);
> `Tenant.data_quality_advanced_enabled` defaults FALSE everywhere
> and is flipped per-tenant after a 14d soak of 240.3.B.

**New endpoints / capabilities:**

- `POST /api/v1/quality/dq-runs/{id}/trends/`, `/scorecards/`, `/anomalies/`, `/root-cause-analysis/` — advanced quality endpoints gated by `data_quality_enabled AND data_quality_advanced_enabled` (Phase 240.3.B).
- `POST /run` (dq-service) now routes by profile-key suffix to the engine-agnostic `DQAdapter`: `*_soda` → `SodaAdapter`, all others → `GXAdapter` (Phase 240.3.A).
- DQ alert delivery across 4 channels (`EMAIL`, `SLACK`, `WEBHOOK`, `PAGERDUTY`) at [hub/apps/dq/clients/](hub/apps/dq/clients/), each with circuit-breaker integration via `hub.apps.core.resilience.service_breakers` (Phase 240.1.A).
- Tenant-scoped DQ alerting rules (`DQAlertingRule`) with comparison operator + threshold + dedup window + retry / dead-letter lifecycle (Phase 240.1.A.5).

**Behaviour changes (additive-only — no MODIFIED endpoints):**

- All hub→dq-service calls now carry `traceparent` + `tracestate` (W3C TraceContext) — `service.name=hub-api` and `service.name=dq-service` spans connect in Tempo (Phase 240.2.C).
- Hub→dq-service POST bodies now carry `X-Internal-Payload-Signature` + `X-Internal-Payload-Timestamp` headers (HMAC-SHA256 over `timestamp + "\n" + body`); dq-service verifies in soak mode (`DQ_REQUIRE_PAYLOAD_SIGNATURE=false`) on day-0, flips to enforce after 7d telemetry confirms 100% Hub coverage (Phase 240.5.G).
- DQ runs that exhaust dq-service retries now route to the dead-letter queue + emit `DQ_ALERT_DEAD_LETTER_OPS_PAGERDUTY` audit events for ops paging (Phase 240.5.A).
- All `logger.*(..., extra={...})` calls in DQ Hub-side files (`views.py`, `services.py`, `service_client.py`, `alerting.py`, `tasks.py`, `clients/*.py`) wrap their dict in `_redact()` from `hub.apps.dq.log_helpers` — recursively strips `row_samples`, `sample_value`, `sample_data_json`, `file_content`, `body`, `raw_data`, `data`, `details_json` keys before log emission (Phase 240.5.F).

**New audit-event codes (registered in [hub/apps/audit/models.py](hub/apps/audit/models.py)):**

- `DQ_RUN_STARTED`, `DQ_RUN_COMPLETED`, `DQ_RUN_FAILED` (Phase 240.0)
- `DQ_ALERT_RULE_CREATED`, `DQ_ALERT_RULE_UPDATED`, `DQ_ALERT_RULE_DELETED` (Phase 240.1.A.5)
- `DQ_ALERT_FIRED`, `DQ_ALERT_DELIVERED`, `DQ_ALERT_DELIVERY_FAILED`, `DQ_ALERT_RETRY_SCHEDULED`, `DQ_ALERT_DEAD_LETTER_OPS_PAGERDUTY` (Phase 240.1.A)
- `DQ_ALERT_CHANNEL_DEGRADED`, `DQ_ALERT_CHANNEL_RECOVERED` (Phase 240.1.A.6 — circuit-breaker)

**New per-tenant flags:**

- `Tenant.data_quality_enabled` — default **True** on existing tenants (no surprise disable per D240.18).  Kill-switch: flip to False to disable the entire DQ feature for the tenant; in-flight runs complete (no abort), subsequent reads return 403 (D240.18 + 240.4.B.2 / OQ240.4).
- `Tenant.data_quality_advanced_enabled` — default **False** everywhere.  Conjunctive with the base flag.  Gates the four 240.3.B advanced endpoints (`/trends/`, `/scorecards/`, `/anomalies/`, `/root-cause-analysis/`).  Per-tenant flip after 14d production stability of the 240.3.B endpoints (D240.18).

**Operational assets:**

- Grafana dashboard at [monitoring/grafana/dashboards/data-quality.json](monitoring/grafana/dashboards/data-quality.json) with run-rate / latency / engine success / queue-depth / alert-delivery panels (Phase 240.5.B.1).
- Prometheus alert rules at [monitoring/prometheus/alerts/dq.yml](monitoring/prometheus/alerts/dq.yml) — 8 alerts covering run-failure-rate, p95 duration regression, circuit-open, alert-delivery, engine-success, queue-depth, audit-write, S3 payload growth (Phase 240.5.B.2).
- Synthetic firing tests at [monitoring/prometheus/alerts/dq-synthetic-firing.yml](monitoring/prometheus/alerts/dq-synthetic-firing.yml) (Phase 240.5.B.4).
- Operational runbook at [docs/runbooks/data-quality.md](docs/runbooks/data-quality.md) — SLOs, alert anchors, capacity sizing, kill switches, rolling-deploy for payload signing, PII redaction contract.
- Trivy DQ-service image vulnerability gate enforced in [.github/workflows/deploy.yml](.github/workflows/deploy.yml) — blocks deploy on CRITICAL/HIGH; pinned by contract test [tests/ci/test_dq_image_vulnerability_scan.py](tests/ci/test_dq_image_vulnerability_scan.py) (Phase 240.5.D).
- Helm-canonical DQ-service configuration at [helm/values.yaml](helm/values.yaml) under `dqService.config.*` — single source of truth replacing the prior `k8s/dq-service/base/` Kustomize tree (Phase 240.1.D).

**Internal (no API surface):**

- Hub-side `_redact()` helper at [hub/apps/dq/log_helpers.py](hub/apps/dq/log_helpers.py); AST-based lint script at [scripts/check_dq_log_extras.py](scripts/check_dq_log_extras.py); pre-commit + CI gates (`check-dq-log-extras` + `lint-dq-log-extras`) — drift safeguard `TestLintRuleParity` pins `_REDACTED_KEYS` ↔ `_FORBIDDEN_KEYS` parity (Phase 240.5.F).
- Post-deploy DQ smoke-test script at [scripts/smoke_tests_dq.sh](scripts/smoke_tests_dq.sh) covering DoD.4: synthetic runs across registered profile keys, alert dry-run for all 4 channels, Grafana DQ board non-zero-data check (Phase 240.DoD.4).

### BREAKING — Phase 227: Structureless contracts now rejected at the API edge

**What changed:** `POST /api/v1/contracts/` and
`PATCH /api/v1/contracts/{id}/` now return **HTTP 400** with
`error.code = "STRUCTURELESS_CONTRACT"` when the submitted /
re-normalised contract has no resolvable
`models[*].fields[*]` AND no `schema.fields[*]`. Asset activation
(`PATCH /api/v1/assets/{id}/ {status: ACTIVE}`) returns the same
code as a blocker; marketplace publish
(`PATCH /api/v1/marketplace/listings/{id}/ {status: PUBLISHED}`)
returns **HTTP 422** with the same code. Pre-227 the API silently
accepted these payloads, persisting rows with `hub_contract_json =
NULL` or empty `models = []`.

The floor is **always-on** per the 2026-04-30 ungate directive — no
feature flag, no per-tenant override, no deprecation period. Wave-3
self-heal handles the bulk of pre-227 structureless rows
automatically; the rest require customer action via the Schema
editor.

**Affected endpoints:**

- `POST /api/v1/contracts/` — 400 `STRUCTURELESS_CONTRACT`
- `PATCH /api/v1/contracts/{id}/` — 400 `STRUCTURELESS_CONTRACT`,
  plus 412 `PRECONDITION_FAILED` when `If-Match` ETag is stale
- `PATCH /api/v1/assets/{id}/` — 400 with structural blocker in
  `error.details.blockers[]`
- `PATCH /api/v1/marketplace/listings/{id}/` — 422
  `STRUCTURELESS_CONTRACT` (both publish paths)
- Internal write paths (`ODPSService.create_odps`,
  `ContractService.link_odps_to_odcs`,
  `ODPSService.normalize_odps`) — same envelope

**New endpoints:**

- `GET /api/v1/contracts/schema/json-schema/?spec=<odcs|odps>` —
  returns the canonical Pydantic-derived JSON Schema with
  `Content-Type: application/schema+json` (IANA registered)
- `GET /api/v1/contracts/?filter=structureless` — TENANT_ADMIN-only
  triage list of structureless contracts in the tenant
- `POST /api/v1/contracts/schema-editor/metrics` — backend OTel
  receiver for Schema-editor adoption telemetry (no client-supplied
  tenant_id; server-derived from session)

**New error codes** (full taxonomy at
[error catalog](docs/mvpdocs/reference/error-codes.md#structureless-contract-codes-phase-227)):

| Code | HTTP | Notes |
| ---- | ---- | ----- |
| `STRUCTURELESS_CONTRACT` | 400 / 422 | `details.subcode` ∈ `{STRUCTURELESS_ODPS_NO_PORTS, STRUCTURELESS_ODCS_NO_SCHEMA, STRUCTURELESS_GENERIC, STRUCTURELESS_CYCLIC_PORTS}` |
| `SCHEMA_TOO_DEEP` | 400 | ODCS nested-properties walker hit `CONTRACTS_MAX_NESTING_DEPTH` (default 20) |
| `INVALID_YAML` | 400 | Unsafe YAML construct rejected by `yaml.safe_load` |
| `PRECONDITION_FAILED` | 412 | `If-Match` ETag mismatch on contract PATCH |
| `PAYLOAD_TOO_LARGE` | 413 | `original_raw` exceeds 2 MB |

**New observability** (Phase 227 L7):

- OTel counters: `contract_validation_failed_total`,
  `contract_structureless_total`, `audit_events_total`,
  `schema_editor_opened_total`, `schema_editor_save_total`
- OTel histograms: `contract_normalization_models_count`,
  `contract_normalization_fields_total_count`,
  `contracts_renormalize_batch_duration_seconds`,
  `schema_editor_time_to_first_save_seconds`
- OTel gauge: `contract_structureless_backlog`
- New audit actions: `CONTRACT_VALIDATION_FAILED`,
  `CONTRACT_STRUCTURELESS_REJECTED`,
  `ASSET_AUTO_REVERTED_STRUCTURELESS`,
  `CONTRACT_BATCH_RENORMALIZED`,
  `ASSET_RESTORED_STRUCTURELESS`
- New Grafana dashboard:
  `monitoring/grafana/dashboards/structureless-contract-rollout.json`
  (UID `hub-structureless-rollout-227`) — 8 panels covering
  rejection rate, source distribution, backlog gauge,
  models-per-contract distribution, batch duration, schema-editor
  adoption funnel, time-to-first-save, asset auto-reverts

**New email types** (Phase 227 Wave 5):

- `ASSET_AUTO_REVERT_WARNING` — T+30 final-warning email sent to
  every TENANT_ADMIN of every tenant whose currently-active
  contracts remain structureless 14 days before the W5 cutover.
  Drives the new `wave5_send_final_warning_notifications`
  management command (W5.1).
- `ASSET_AUTO_REVERTED_NOTIFICATION` — per-asset notification
  emitted by the apply-asset-revert path right after an asset is
  demoted to DRAFT. Each TENANT_ADMIN of the affected tenant gets
  one email + one in-app `UserNotification` (governance category)
  carrying the asset name, the structureless contract id, the
  previous status, and the Schema-editor + Asset-detail
  deep-links. Wired into `_maybe_revert_asset`; best-effort —
  notification dispatch failures DO NOT roll back the demotion
  (which is the load-bearing operation).

**New management commands** (Phase 227 Wave 5):

- `wave5_send_final_warning_notifications --deadline=YYYY-MM-DD`
  — broadcasts the T+30 final warning to every tenant with at
  least one structureless ACTIVE contract. Mirrors the W4 driver
  conventions: idempotency-via-audit-row (`ASSET_AUTO_REVERT_WARNING_NOTIFIED`),
  per-recipient fail-soft, all-failed-batch-leaves-no-audit-row
  (so retries can self-heal), `--dry-run`, `--audit-output`,
  `--force`, `--tenant-id`, `--all-tenants`. Default scope guard
  excludes already-clean tenants so the warning doesn't reach
  customers who have already remediated.

**New audit actions** (Phase 227 Wave 5):

- `ASSET_AUTO_REVERT_WARNING_NOTIFIED` — written by the W5.1
  driver after a successful per-tenant dispatch. Powers the
  driver's idempotency check.

**New webhook event types** (Phase 227 W3.4):

- `contract.batch_renormalized` — emitted once per `renormalize_contracts
  --apply` batch per affected tenant. Resource is the tenant
  (`resource_type="TENANT"`, `resource_id=<tenant_uuid>`); payload `data`
  carries `{run_id, tenant_id, processed, healed, residual, failed}`.
  Subscribers wanting the rollup of bulk migrations subscribe here
  instead of `contract.updated` (which fires per-row when
  `--silent-events` is omitted).

**New `renormalize_contracts --apply` summary fields** (Phase 227 W3.5):

- `per_tenant` — map of `<tenant_uuid>` → `{processed, healed, residual,
  failed}` aggregated across batches.
- `residue_tenants` — sorted list of `<tenant_uuid>`s where `residual +
  failed > 0`. Drives Wave 4 follow-up email scoping.

**New management-command flags** on `renormalize_contracts`:

- `--apply` — re-normalise structureless contracts (vs. default
  `--dry-run` diagnosis)
- `--apply-asset-revert` — demote ACTIVE assets backed by
  contracts that REMAIN structureless after re-normalisation
- `--silent-events` — suppress per-contract webhooks; emit one
  batch summary
- `--checkpoint-table=<name>` — resumable across crashes
- `--output=count` — emit a single integer for the daily
  pushgateway cron

**New migrations:**

- `contracts/0023_migration_checkpoint.py` — adds `MigrationCheckpoint`
  table for resumable bulk operations
- `contracts/0024_unrevert_structureless_assets.py` — reversible
  data migration that restores assets demoted by
  `--apply-asset-revert`

**Migration paths:**

- SDK consumers: see
  [migration guide](docs/migration-guides/structureless-contracts-deprecation.md)
- Operators triaging tenants: see
  [ops runbook](docs/runbooks/structureless-contracts.md)
- Canonical contract shapes per spec version:
  [`docs/CONTRACTS.md`](docs/CONTRACTS.md)

### Removed

- `VITE_FEATURE_SCHEMA_EDITOR_ENABLED` frontend feature flag —
  Schema editor tab now visible to every user with the existing
  modify-role permission, per the 2026-04-30 ungate directive.
- `contracts.structural_floor.enabled` and
  `contracts.schema_editor.enabled` backend feature flags — never
  shipped; the directive retired flag-gating before registration.

### Internal

- New OTel metric module helpers in
  `hub.apps.contracts.normalization_metrics`
- New `hub.apps.contracts.structural_floor.enforce_structural_floor`
  module — single source of truth for the floor invariant
- New `MigrationCheckpoint` model + tests for resumable bulk ops
- 144 functional tests + 3 performance benchmarks added under
  `hub/apps/contracts/tests/test_*.py` and
  `hub/apps/marketplace/tests/test_marketplace_publish_structural_blocker.py`

### Frontend — Phase 276: Audit & Remediation (2026-05-12)

- **Audit**: 9-pass static review of frontend codebase produced 24 findings
  (8 P0, 10 P1, 6 P2). Capability coverage matrix, persona journey audit,
  UX heuristics, system design, FE↔BE contracts, infra/security, CI/quality
  gates, and docs/DX all covered.
- **AUTH-007 sweep**: `useActiveTenantId()` centralized hook replaces 40+
  direct `user.tenant_id` reads. Multi-tab session sync via `storage` events.
- **Browser-console capture**: e2e harness now fails tests on uncaught
  browser console errors (with configurable allowlist).
- **New hooks**: `useNotificationStream()` (SSE), `useRetryAfter()` (429
  exponential backoff), `ThemeProvider` (dark mode toggle).
- **Infrastructure**: CSP header in nginx config, `.env` pre-commit guard,
  OpenAPI→FE-types CI drift gate, Storybook scaffold.
- **XSS audit**: 0 `dangerouslySetInnerHTML` found — project clean.
