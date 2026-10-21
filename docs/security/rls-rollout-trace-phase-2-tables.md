# RLS Rollout Trace — Phase 2 Tables

## Scope

Trace map for `260.B-RLS-2` per-table rollout:

- datasets -> `datasets`
- users -> `users`
- user_tenant_memberships -> `user_tenant_memberships`
- audit_events -> `audit_events`
- contracts -> `contracts`
- marketplace_listings -> `listings`
- jobs -> `jobs`
- billing_subscriptions -> `subscriptions`
- compliance_runs -> `compliance_runs`
- search_indices -> `search_index`
- semantic_ontologies -> `semantic_tenant_ontologies`
- mesh_domains -> `data_mesh_domains`

## Enforcement Pattern

- PostgreSQL policy: `tenant_isolation` per table.
- Read gate:
  - allow when `app.rls_<table>_enabled != 'true'` (kill switch),
  - otherwise require `tenant_id::text = current_setting('app.current_tenant_id', true)`.
- Write gate:
  - always enforce tenant match via `WITH CHECK`.

## Runtime Context

- HTTP path: `TenantScopingMiddleware` applies the tenant GUC and every
  `RLS_*_ENABLED` table flag, transaction-locally inside the request's
  transaction, gated behind the `RLS_REQUEST_PATH_ENABLED` master kill
  switch (W1.20 / oss-release-remediation D2). Transaction-local GUCs
  are mandatory under PgBouncer transaction pooling.
- Worker path: table access expected under explicit `tenant_context(...)` wrappers.
- Management command path: admin alias routing with explicit per-tenant loops where required.

## Pre-Tenant Identity Resolution

- Any lookup that must see identity rows BEFORE a tenant GUC exists
  (login, API-key extraction, JWT user resolution, membership checks)
  routes through `hub.apps.auth.db_aliases.user_lookup_alias()` — the
  BYPASSRLS admin alias in the production role shape
  (`meshant_app` default / `meshant_admin` admin), the default
  connection everywhere else. The middleware's own resolution queries
  use the same seam (W1.20).
- This is intentionally scoped to pre-tenant identity lookups only;
  post-auth access remains tenant-scoped.

## Validation

- Cross-tenant baseline harness: `tests/integration/test_rls_baseline.py`.
- Phase-2 table coverage assertion includes all rollout tables listed above.
- Middleware GUC arming + table-flag propagation are validated by
  `hub/apps/auth/tests/test_rls_middleware_guc.py` (real `current_setting`
  probes) and the settings ↔ deployed-policy inventory sync in
  `hub/apps/auth/tests/test_rls_guc_settings_sync.py` (W1.20).
