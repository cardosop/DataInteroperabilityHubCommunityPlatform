# RLS Rollout Trace — Assets Pilot

## Scope

This trace maps every `Asset` ORM access surface to the enforcement strategy used for the `assets` pilot-table RLS rollout (`260.B-RLS-1.3`).

Chosen strategy:

- HTTP/request path: `TenantScopingMiddleware` arms the GUCs
  (`app.current_tenant_id`, `app.rls_assets_enabled`) transaction-locally
  inside the request's transaction (W1.20 / oss-release-remediation D2).
  The whole path is gated behind the `RLS_REQUEST_PATH_ENABLED` master
  kill switch (default True — armed); `RLS_ASSETS_ENABLED` disables the
  assets policy alone. Arming fails closed: no tenant → NULL/empty GUC
  → the policy hides every row.
- Worker/background path: explicit `tenant_context(tenant_id)` wrapping
- Management/cron path: admin-role execution (`meshant_admin`) plus explicit per-tenant iteration where needed

## HTTP And API Surfaces

- `hub/apps/assets/views.py`
- `hub/apps/assets/views_optimized.py`
- `hub/apps/search/views.py`
- `hub/apps/graphql_graphene/schema.py`
- `hub/apps/graphql/schema.py`

Coverage:

- Request pipeline applies tenant + RLS flag GUCs in `hub/apps/auth/middleware.py`
  (W1.20): the request runs inside `transaction.atomic()` with `SET LOCAL`
  GUCs — transaction-local is mandatory under PgBouncer transaction
  pooling (a session-level SET would leak onto the next pooled client).
- `RLS_ASSETS_ENABLED` is an explicit per-table kill switch and
  `RLS_REQUEST_PATH_ENABLED` the master arming switch (both default True).
- The middleware's own pre-tenant lookups route through
  `hub.apps.auth.db_aliases.user_lookup_alias()` (BYPASSRLS admin alias
  in the production role shape).

## Worker And Async Surfaces

- `hub/apps/jobs/tasks_base.py` (shared job execution wrapper)
- `hub/apps/search/tasks.py` (asset search-vector update path)
- `hub/apps/orchestration/workflows/asset_creation.py`
- `hub/apps/orchestration/workflows/product_creation.py`

Pilot hardening applied:

- `hub/apps/search/tasks.py` now accepts `tenant_id` and runs `update_asset_search_vector` inside `tenant_context(...)`.
- `hub/apps/assets/signals.py` now propagates `tenant_id` when enqueueing asset search-vector updates.

## Signals

- `hub/apps/assets/signals.py`
- `hub/apps/semantic/signals.py`

Coverage:

- Signal-triggered background work now preserves tenant scope on the asset search-vector enqueue path.
- Deferred callback context hardening from `B-RLS-0.7` remains in place for tenant-scoped deferred operations.

## Management Commands And Cron-Invoked Commands

- `hub/apps/assets/management/commands/cleanup_orphan_drafts.py`
- `hub/apps/semantic/management/commands/migrate_triples_to_named_graphs.py`
- `hub/apps/semantic/management/commands/rebuild_fuseki.py`
- `hub/apps/semantic/management/commands/backfill_tombstones.py`
- `hub/apps/contracts/management/commands/renormalize_contracts.py`

Coverage:

- Command execution follows admin-alias routing (`meshant_admin`) from `B-RLS-0.5`.
- Per-tenant command loops/context wrapping from `B-RLS-0.6` remain the standard for tenant-scoped command behavior.

## Validation Notes

- Pilot acceptance tests for `assets` RLS behavior are implemented at `tests/integration/test_rls_assets_pilot.py`.
- Existing cross-table baseline harness remains at `tests/integration/test_rls_baseline.py`.
- W1.20 request-path arming pins (real DB GUC probes, non-BYPASSRLS
  probe-role enforcement, full-stack planted-unfiltered-view pins):
  `hub/apps/auth/tests/test_rls_middleware_guc.py`,
  `hub/apps/auth/tests/test_rls_request_path_arming.py`,
  `hub/apps/auth/tests/test_rls_guc_settings_sync.py` (settings ↔
  deployed-policy GUC inventory, both directions), and
  `hub/apps/auth/tests/test_rls_middleware_preauth_alias.py`.
