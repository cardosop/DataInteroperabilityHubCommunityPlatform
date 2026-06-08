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

- HTTP requests: middleware sets transaction-local GUCs:
  - `app.current_tenant_id`
  - `app.rls_<table>_enabled`
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
  tenant-scoped model includes a paired RLS policy migration.

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
