# Threat Model — Tenant Isolation (Post-RLS)

## Scope

This document captures the post-RLS tenant-isolation architecture after
Phase `260.B` rollout (`assets` pilot + phase-2 tables) and the
remaining residual risks.

## Security Objective

Prevent cross-tenant data disclosure or mutation even when application
code has filtering bugs, by enforcing tenant isolation at both:

- application layer (request/worker tenant scoping), and
- database layer (PostgreSQL Row-Level Security).

## Architecture Summary

### Layer 1 — Application scoping

- HTTP requests (W1.20 / oss-release-remediation D2): the
  `TenantScopingMiddleware` resolves the request tenant, then wraps
  the rest of the request in ONE `transaction.atomic()` and sets the
  GUCs transaction-locally (`SET LOCAL`):
  - `app.current_tenant_id` — the resolved tenant; NULL/empty for
    anonymous requests (fail-closed: policies hide every row)
  - `app.rls_<table>_enabled` — one per deployed policy, mapped from
    the paired `RLS_<TABLE>_ENABLED` settings kill switch
  - The whole path is gated behind the `RLS_REQUEST_PATH_ENABLED`
    master kill switch (default True — armed). Transaction-local GUCs
    are mandatory under PgBouncer transaction pooling; they evaporate
    at COMMIT/ROLLBACK so a pooled connection never leaks scope.
  - Pre-tenant identity resolution (API keys, JWT users, memberships)
    routes through `hub.apps.auth.db_aliases.user_lookup_alias()` —
    the BYPASSRLS admin alias in the production role shape
    (`meshant_app` default / `meshant_admin` admin).
- Worker and deferred paths: must run tenant-scoped operations under
  `tenant_context(tenant_id)`.
- Management commands and global maintenance paths run on the
  `admin` alias (`meshant_admin`, `BYPASSRLS`) and explicitly iterate
  tenant workloads.

### Layer 2 — Database enforcement (RLS)

- Tenant-scoped tables have explicit RLS `CREATE POLICY` migrations.
- Standard policy shape:
  - `USING`: tenant match OR table kill-switch off
  - `WITH CHECK`: tenant match for writes
- CI gate `lint-rls-policies` enforces that any newly introduced
  tenant-scoped model includes a paired RLS policy migration; the
  W1.20 inventory sync
  (`hub/apps/auth/tests/test_rls_guc_settings_sync.py`) pins every
  deployed policy GUC to its `RLS_*_ENABLED` settings kill switch and
  vice versa.

## Trust Boundaries

- External callers -> API boundary
- API/worker process -> PostgreSQL boundary
- Admin-role maintenance boundary (`meshant_admin`) vs app-role
  transactional boundary (`meshant_app`/default app role)

## Primary Threats Addressed

- Missing ORM `.filter(tenant_id=...)` on read paths
- Cross-tenant accidental updates/deletes on write paths
- Worker/deferred callbacks executing without tenant context
- Schema evolution adding a tenant-scoped model without RLS policy

## Residual Risks (Post-RLS)

1. **Out-of-transaction caching leaks**
   - Risk: tenant-scoped data cached without tenant-qualified keying.
   - Mitigation: enforce tenant-aware cache keys and avoid sharing
     mutable tenant data in process-global caches.

2. **Admin alias misuse**
   - Risk: business paths accidentally executed with `DATABASES["admin"]`
     bypass RLS.
   - Mitigation: limit admin alias use to explicit command/maintenance
     contexts; code review + audit logging for admin-alias call sites.

3. **Long-lived background context drift**
   - Risk: deferred jobs/signals lose tenant context.
   - Mitigation: pass `tenant_id` explicitly into enqueue payloads and
     restore scope via `tenant_context` at execution.

4. **Raw SQL outside policy assumptions**
   - Risk: unsafe SQL/GUC handling in custom code.
   - Mitigation: parameterize SQL, enforce allowlisted role switching,
     and keep RLS acceptance tests in CI.

5. **Kill-switch overuse**
   - Risk: prolonged `app.rls_<table>_enabled=false` weakens DB
     enforcement.
   - Mitigation: kill-switch as temporary incident control only, with
     runbook-driven rollback and tracked expiry.

6. **Pre-tenant resolution failure (arming world)**
   - Risk: any query that must read identity rows before the tenant
     GUC exists (login, token refresh with no access cookie, new
     pre-auth surfaces) sees zero rows under an enforcing role — the
     fail-closed direction, surfacing as 401/403/empty, never leaks.
   - Mitigation: pre-tenant lookups MUST route through
     `user_lookup_alias()`; new surfaces are caught by the staging
     soak (M1 gate) and the W1.8 stop-the-line check.

7. **Session-level GUC leakage via pooling**
   - Risk: a session-level `SET` on a PgBouncer transaction-pooled
     connection leaks one tenant's scope into the next client.
   - Mitigation: the middleware only ever sets transaction-local GUCs
     inside the request transaction (pinned by the no-leak tests in
     `test_rls_middleware_guc.py` /
     `test_rls_request_path_arming.py`); `tenant_context` is likewise
     transaction-scoped.

8. **Streaming responses render outside the armed transaction**
   - Risk: a streaming body generated after the middleware transaction
     commits runs without GUCs — fail-closed to empty results.
   - Mitigation: fail-closed direction is safe; any streaming surface
     that must read tenant data needs explicit `tenant_context`
     wrapping inside the generator.

## Detection And Assurance

- CI:
  - `lint-rls-policies`
  - `test-rls` baseline suite (`pytest -m rls`)
- Runtime:
  - denied-access metrics and audit events
  - rollout performance snapshots (`pg_stat_statements`) and canary
    guardrails in RLS runbooks

## Operational Guidance

- Keep dual-layer protection (app + DB) during stabilization.
- Only consider removing redundant app-layer tenant filters after
  sustained production stability and explicit follow-up change approval.
