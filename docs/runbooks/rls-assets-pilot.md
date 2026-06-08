# Runbook — Assets RLS Pilot

## Purpose

Operational runbook for `260.B-RLS-1.4` and `260.B-RLS-1.5`:

- performance verification with `pg_stat_statements`
- staged canary rollout for `RLS_ASSETS_ENABLED`

## Prerequisites

- `pg_stat_statements` enabled on staging and production Postgres
- `DATABASE_URL_ADMIN` points to an admin-capable DB role
- assets RLS migration applied

## 1) Pre-migration Baseline Snapshot

Capture baseline (top-20 `assets` touching queries by total execution time):

```bash
python scripts/rls_assets_pg_stat.py snapshot \
  --output artifacts/rls-assets/pgstat-baseline.json \
  --limit 20
```

Store the artifact in CI/build output or deployment ticket.

## 2) 24h Post-deploy Snapshot And Regression Check

Capture a second snapshot 24h after staging rollout:

```bash
python scripts/rls_assets_pg_stat.py snapshot \
  --output artifacts/rls-assets/pgstat-post24h.json \
  --limit 20
```

Compare and fail on regressions above 20% mean execution-time increase:

```bash
python scripts/rls_assets_pg_stat.py compare \
  --baseline artifacts/rls-assets/pgstat-baseline.json \
  --current artifacts/rls-assets/pgstat-post24h.json \
  --threshold-pct 20
```

If regressions are reported:

- create an incident ticket labeled `rls-assets-regression`
- hold canary progression
- attach both snapshots and the compare output

## 3) Production Canary Rollout

### Phase A — Safety deploy (`RLS_ASSETS_ENABLED=false`)

- deploy chart with `RLS_ASSETS_ENABLED="false"` (api + worker)
- verify zero auth/runtime errors for 30 minutes

### Phase B — 5% canary (`RLS_ASSETS_ENABLED=true`)

- set canary values so 5% traffic receives `RLS_ASSETS_ENABLED="true"`
- monitor for 24h
- guardrails:
  - `5xx` rate does not regress >10% from baseline
  - p95 latency on asset list/detail endpoints does not regress >20%
  - `cross_tenant_denied_total` remains non-zero and stable

### Phase C — 50% canary

- increase canary weight to 50%
- monitor for 24h with the same guardrails

### Phase D — 100% rollout

- set 100% traffic to `RLS_ASSETS_ENABLED="true"`
- remove temporary canary split
- keep heightened monitoring for 24h

## 4) Staging Acceptance Checks

Run:

```bash
python -m pytest tests/integration/test_rls_assets_pilot.py -m rls --database=meshant_app -q
```

Expected:

- tenant-scoped ORM query returns only tenant-owned assets
- raw cursor query with no tenant GUC returns `0` rows
- setting `SET LOCAL app.rls_assets_enabled='off'` exposes all seeded rows

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
