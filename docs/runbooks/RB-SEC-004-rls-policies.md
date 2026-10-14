# RB-SEC-004 — RLS Policy Management

**Owner**: Security Engineering
**Severity**: Critical (tenant data isolation)

## Purpose

Every model with a `tenant_id` ForeignKey MUST have a paired RLS (Row-Level Security) `CREATE POLICY` migration. This runbook covers the lifecycle: adding RLS to new models, auditing existing coverage, and triaging RLS leaks.

## Quick Reference

```bash
# Check RLS coverage (CI gate)
python scripts/lint_rls_policies.py --fail-on-new

# Check a specific app
python scripts/lint_rls_policies.py --app billing

# List all exemptions
cat scripts/exemptions/rls_exemptions.yaml
```

## Adding RLS to a New Model

1. Follow the template in `docs/rls-migration-template.md`
2. CREATE POLICY before ENABLE ROW LEVEL SECURITY
3. Naming: `tenant_isolation_{table_name}`
4. Direct FK — the standard policy shape (string compare, NOT a
   `::uuid` cast — every deployed policy compares `tenant_id::text`):

   ```sql
   CREATE POLICY tenant_isolation ON <table>
   USING (
       current_setting('app.rls_<table>_enabled', true) <> 'true'
       OR tenant_id::text = current_setting('app.current_tenant_id', true)
   )
   WITH CHECK (
       tenant_id::text = current_setting('app.current_tenant_id', true)
   );
   ```

   The `app.rls_<table>_enabled` OR-branch is the per-table kill
   switch: unset it behaves as ENFORCED (NULL/'' propagates to the
   tenant match, which hides everything); `'false'` opens reads for
   forensic inspection; writes stay tenant-bound via WITH CHECK.
5. Ship the paired `RLS_<TABLE>_ENABLED` settings entry (default True)
   in `hub/settings.py` — the W1.20 inventory sync
   (`hub/apps/auth/tests/test_rls_guc_settings_sync.py`) fails the
   suite on any policy without a kill-switch setting, and vice versa.
6. Run pre-flight tenant_context audit (285.14.1.3)
7. Document findings in migration docstring

## Triage: RLS Leak Detected

If `lint_rls_policies.py` reports a violation:

1. Identify the model and its `tenant_id` field
2. Check if an exemption applies (see `scripts/exemptions/rls_exemptions.yaml`)
3. If no exemption: create RLS migration following the template
4. If exemption: add entry to `rls_exemptions.yaml` with reason, review_date, sunset_date
5. Re-run lint to verify

## Exemption Lifecycle

- Review all exemptions monthly
- Remove stale exemptions where sunset_date has passed (model must get RLS or new exemption)
- Do NOT let exemptions accumulate — each one is a tenant isolation gap

## CI Enforcement

- `lint-rls-policies` job in `.github/workflows/ci.yml`
- Blocks PRs that add new `tenant_id` columns without paired RLS migrations
- Exemptions reviewed in `validate-security` job
- W1.20 inventory sync: `hub/apps/auth/tests/test_rls_guc_settings_sync.py`
  pins every deployed policy GUC ↔ `RLS_*_ENABLED` settings kill switch
  (bidirectional, read from `pg_policies` at runtime).

## Request-Path Arming (W1.20) — Operations

`TenantScopingMiddleware` arms RLS on every request: the request runs
inside `transaction.atomic()` with `SET LOCAL` GUCs (the tenant +
every table flag). Transaction-local GUCs are mandatory — staging and
production route through PgBouncer transaction pooling, and a
session-level SET would leak onto the next client reusing the pooled
connection. `SET LOCAL` evaporates at COMMIT/ROLLBACK.

### Kill switches

| Switch | Effect |
| --- | --- |
| `RLS_REQUEST_PATH_ENABLED` | Master arming switch (default `True`). `false` disables the whole request-path arming — no GUCs are set and policies behave as unarmed. |
| `RLS_<TABLE>_ENABLED` | Per-table switch (default `True`). `false` opens that table's USING clause for reads (forensic mode); WITH CHECK stays tenant-bound. |

### Arming failure modes — all fail CLOSED

- Arming failure (GUCs cannot be set): the middleware returns
  `503 SERVICE_UNAVAILABLE` (`RLS_ARMING_FAILED`) — the request never
  runs unscoped.
- Anonymous request / unresolvable tenant: `app.current_tenant_id`
  is NULL/empty → every tenant policy hides every row (empty results,
  never cross-tenant rows).
- Kill switch off + enforcing role: no GUC → policies hide everything.
- Streaming responses: the body renders after the middleware
  transaction commits, without GUCs → fail-closed to empty.

### Rollout & soak procedure

1. Deploy with `RLS_REQUEST_PATH_ENABLED=true` (default) on staging.
2. Soak ≥72h (M1 gate): monitor request volume/errors; a fail-closed
   regression shows as empty-result spikes (HTTP 200 with empty
   payloads), NOT 500s — correlate with the
   `rls_arming_failed` error log line (arming itself failed → 503).
3. Triage any empty-result regression: either the view's queryset was
   missing its tenant filter (W1.4a class) — fix the queryset — or a
   pre-tenant identity lookup needs `user_lookup_alias()` routing
   (`hub/apps/auth/db_aliases.py`).
4. Emergency rollback: set `RLS_REQUEST_PATH_ENABLED=false` (per-table
   rollback: the matching `RLS_<TABLE>_ENABLED=false`) — no deploy
   required.
5. Production arming happens after the M1 staging soak sign-off.
