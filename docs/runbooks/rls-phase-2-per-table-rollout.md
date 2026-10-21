# Runbook — RLS Phase 2 Per-Table Rollout

## Scope

Operational guide for `260.B-RLS-2` rollout tables:

- `datasets`
- `users`
- `user_tenant_memberships`
- `audit_events`
- `contracts`
- `listings` (task label: marketplace_listings)
- `jobs`
- `subscriptions` (task label: billing_subscriptions)
- `compliance_runs`
- `search_index` (task label: search_indices)
- `semantic_tenant_ontologies` (task label: semantic_ontologies)
- `data_mesh_domains` (task label: mesh_domains)

## Prerequisites

- RLS migrations applied for each target table.
- `DATABASE_URL_ADMIN` points to an admin-capable role.
- `pg_stat_statements` enabled in the target environment.
- Canary deployment support available in Helm release pipeline.

## 1) Capture Baseline Snapshot (Per Table)

```bash
TABLE="<table_name>"
python scripts/rls_table_pg_stat.py snapshot \
  --table "${TABLE}" \
  --output "artifacts/rls-phase2/${TABLE}/pgstat-baseline.json" \
  --limit 20
```

## 2) Capture 24h Snapshot And Compare

```bash
TABLE="<table_name>"
python scripts/rls_table_pg_stat.py snapshot \
  --table "${TABLE}" \
  --output "artifacts/rls-phase2/${TABLE}/pgstat-post24h.json" \
  --limit 20

python scripts/rls_table_pg_stat.py compare \
  --baseline "artifacts/rls-phase2/${TABLE}/pgstat-baseline.json" \
  --current "artifacts/rls-phase2/${TABLE}/pgstat-post24h.json" \
  --threshold-pct 20
```

If compare exits non-zero:

- stop canary progression for the table,
- open a regression incident,
- attach baseline/current artifacts and compare output.

## 3) Canary Sequence (Per Table)

1. Deploy with `<TABLE_FLAG>=false`.
2. Flip `<TABLE_FLAG>=true` for 5% traffic and monitor 24h.
3. Expand to 50% and monitor 24h.
4. Expand to 100%.

Guardrails:

- endpoint p95 latency regression <= 20%
- error-rate regression <= 10%
- no cross-tenant access regressions in logs and integration checks

## 4) Validation Command

Run baseline RLS integration harness:

```bash
python -m pytest tests/integration/test_rls_baseline.py -m rls --database=meshant_app -q
```

Expected:

- all parameterized tenant-scoped tables remain zero-visible without tenant GUC under `meshant_app`
- admin role assertions continue to pass

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
