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

- HTTP path: `TenantScopingMiddleware` applies tenant GUC and all `RLS_*_ENABLED` table flags.
- Worker path: table access expected under explicit `tenant_context(...)` wrappers.
- Management command path: admin alias routing with explicit per-tenant loops where required.

## Users Login Special-Case

- Login endpoint user lookup now uses `User.objects.using("admin")` to preserve anonymous email lookup semantics even when `users` table RLS is enabled and request has no tenant GUC yet.
- This is intentionally scoped to login lookup only; post-auth access remains tenant-scoped.

## Validation

- Cross-tenant baseline harness: `tests/integration/test_rls_baseline.py`.
- Phase-2 table coverage assertion includes all rollout tables listed above.
- Middleware table-flag propagation remains validated by `hub/apps/auth/tests/test_rls_middleware_guc.py`.
