# B-RLS-0.5 Management Command Audit

Date: 2026-05-05

## Scope

Audit requested in `260.B-RLS-0.5.4` for management commands to confirm:

- command execution uses BYPASSRLS connection (`DATABASES['admin']` alias), and
- tenant-scoped logic uses explicit `tenant_context(...)` where applicable.

## Global Enforcement

- `hub/manage.py` now enables command-mode DB routing by default (except runtime/test commands) and auto-appends `--database admin` for migration-style commands.
- `hub/db_router.py` now includes `ManagementCommandAdminRouter`, which routes ORM reads/writes to the `admin` alias when command mode is enabled.
- `hub/settings.py` now defines `DATABASES['admin']` with same engine/host/port/name as `default`, admin credentials, and router order includes `ManagementCommandAdminRouter`.

## Per-Command Results

- `hub/apps/audit/management/commands/archive_old_audit_events.py` — Cross-tenant archival command; no per-tenant iteration required (`tenant_context`: N/A).
- `hub/apps/contracts/management/commands/migrate_contracts_to_odps.py` — Contract migration path uses explicit tenant filtering options; no tenant iteration loop in command body (`tenant_context`: N/A).
- `hub/apps/contracts/management/commands/renormalize_contracts.py` — Global/filtered renormalization command; tenant-aware outputs already keyed by tenant IDs, no explicit tenant iteration block in command entrypoint (`tenant_context`: N/A).
- `hub/apps/contracts/management/commands/validate_migration.py` — Validation/reporting command; tenant-scope handled by query filters (`tenant_context`: N/A).
- `hub/apps/contracts/management/commands/seed_contract_lineage.py` — **Updated**: wraps seeded tenant execution with `tenant_context(str(tenant.id))`.
- `hub/apps/contracts/management/commands/warm_odps_ref_cache.py` — Cache warm-up command; tenant semantics are query-driven and non-iterative (`tenant_context`: N/A).
- `hub/apps/orchestration/management/commands/cleanup_workflow_state.py` — Workflow cleanup command; no explicit tenant iteration block (`tenant_context`: N/A).
- `hub/apps/orchestration/management/commands/process_workflows.py` — Workflow processor command, global queue semantics (`tenant_context`: N/A).
- `hub/apps/orchestration/management/commands/recover_failed_workflows.py` — Recovery command, global queue semantics (`tenant_context`: N/A).
- `hub/apps/billing/management/commands/billing_cleanup.py` — Global cleanup command; no explicit per-tenant loop (`tenant_context`: N/A).
- `hub/apps/billing/management/commands/reconcile_stripe.py` — Global reconciliation command; no explicit per-tenant loop (`tenant_context`: N/A).
- `hub/apps/baas/management/commands/generate_billing_reports.py` — Report generation by filters/scopes, no explicit tenant-iteration block (`tenant_context`: N/A).
- `hub/apps/baas/management/commands/billing_report_cleanup.py` — Global report cleanup command (`tenant_context`: N/A).
- `hub/apps/users/management/commands/ensure_e2e_user_roles.py` — **Updated in review**: each tenant-scoped user provisioning block now executes under `tenant_context(str(tenant.id))`.
- `hub/apps/users/management/commands/ensure_user_tenant_memberships.py` — **Updated in review**: per-user membership repair now executes under `tenant_context(str(user.tenant_id))`.
- `hub/apps/scheduled_ingestion/management/commands/detect_and_remediate_stuck_runs.py` — Queue/remediation command, global workflow semantics (`tenant_context`: N/A).
- `hub/apps/scheduled_ingestion/management/commands/retry_failed_dlq_sync.py` — Retry command, global DLQ semantics (`tenant_context`: N/A).
- `hub/apps/marketplace/management/commands/expire_entitlements.py` — Expiration command, global entitlement semantics (`tenant_context`: N/A).
- `hub/apps/webhooks/management/commands/rotate_webhook_encryption_key.py` — Key-rotation command, global security operation (`tenant_context`: N/A).
- `hub/apps/semantic/management/commands/migrate_triples_to_named_graphs.py` — **Updated**: wraps each tenant iteration with `tenant_context(tid)`.
- `hub/apps/compliance/management/commands/migrate_compliance_runs_v2.py` — Migration command with global/backfill semantics (`tenant_context`: N/A).
- `hub/apps/integrations/management/commands/harvest_dados_gov_br_direct.py` — **Updated**: wraps selected tenant harvest execution with `tenant_context(str(tenant.id))`.
- `hub/apps/integrations/management/commands/harvest_ckan.py` — **Updated**: wraps selected tenant harvest execution with `tenant_context(str(tenant.id))`.
- `hub/apps/rate_limiting/management/commands/reset_e2e_auth_rate_limits.py` — Global reset operation (`tenant_context`: N/A).

## Validation

- `pytest`:
  - `hub/apps/core/tests/test_admin_db.py`
  - `hub/tests/test_management_command_admin_router.py`
  - `hub/tests/test_settings_admin_alias.py`
  - `hub/tests/test_db_router.py`
  - Result: `29 passed`
- Command load checks:
  - `python hub/manage.py harvest_ckan --help`
  - `python hub/manage.py harvest_dados_gov_br_direct --help`
  - `python hub/manage.py migrate_triples_to_named_graphs --help`
  - `python hub/manage.py seed_contract_lineage --help`
  - Result: success (all commands load/parse).

## Review Fixes (2026-05-05)

- Root-cause fix: `tenant_context()` previously restored GUC by rolling back to a savepoint, which also rolled back caller writes done inside the context.
- `hub/apps/tenants/request_tenant.py` now captures previous `app.current_tenant_id` and restores it with `SET LOCAL` / `DEFAULT` (no data rollback).
- Added regression guard: `hub/apps/tenants/tests/test_tenant_context.py::test_writes_inside_context_are_not_rolled_back`.
- Post-fix validation suite:
  - tenant context tests
  - command tests (`ensure_e2e_user_roles`, `ensure_user_tenant_memberships`)
  - admin routing/settings tests
  - Result: `41 passed`.
