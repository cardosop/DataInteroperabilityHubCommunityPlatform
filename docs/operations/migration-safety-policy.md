# Database Migration Safety Policy — Meshant Platform

**Last updated:** 2026-09-02 (U.7 data rehearsal + data-loss veto section)
**Applies to:** All Django apps under `hub/apps/`
**Enforced by:** CI gate `lint-rls-policies` + `check_migrations`

## Backwards-Incompatible Migration Rules

### 1. No destructive changes without a deprecation cycle

- **Column removal**: Deprecate in release N (set `null=True`, `blank=True`, stop writing). Remove in release N+1.
- **Table removal**: Deprecate in release N (stop writing, keep reads). Remove in release N+1.
- **Column rename**: Use `RenameField` migration (Django built-in). Never `RemoveField` + `AddField`.
- **Data type change**: Create new column, backfill data, switch reads, drop old column. 2-release cycle.

### 2. NOT NULL columns on existing tables

- Must have a `default` value in the migration.
- Must be backfilled via `RunPython` BEFORE the `AlterField` that adds `NOT NULL`.
- Strategy: `AddField(null=True, default=X)` → `RunPython(backfill)` → `AlterField(null=False)`.
- Exception: new tables (no existing rows) — direct `NOT NULL` is fine.

### 3. Unique constraints and indexes

- Add concurrently via `AddIndexConcurrently` (Django 5.1+) on tables > 100K rows.
- Unique constraints on large tables: validate via `ValidateConstraint` before enforcing.
- Index creation on production: schedule during low-traffic window (02:00-04:00 UTC).

### 4. Foreign key changes

- Adding `ForeignKey`: must set `on_delete` explicitly (no default).
- Removing `ForeignKey`: deprecate in release N (set `null=True, db_constraint=False`), remove in N+1.
- Changing `on_delete` from `CASCADE` to `PROTECT`: requires data audit first (no orphaned rows).

## Squash Threshold

- **Trigger**: >200 migration files in a single Django app.
- **Procedure**:
  1. `python manage.py squashmigrations <app> <start> <end> --squashed-name squashed_0001`
  2. Manually resolve conflicts in the squashed migration.
  3. Run `python manage.py migrate <app>` on staging DB — verify zero data loss.
  4. Commit squashed migration + delete individual squashed files.
  5. Run full test suite (`pytest hub/apps/<app>/`).
- **CI enforcement**: `scripts/check_migration_count.py` fails CI when any app exceeds 200.

## Pre-Merge Review Requirements

### Every migration PR must include:

1. **Migration plan** in the PR description:
   ```
   **Migration:** 0042_add_tenant_id_to_assets
   **App:** assets
   **Backwards compatible:** Yes / No (explain if No)
   **Downtime required:** None / <5s / <5min / >5min (explain)
   **Data backfill:** None / RunPython / management command (link)
   **RLS policy added:** Yes / No (required for new models with tenant_id)
   ```

2. **Review checklist**:
   - [ ] `makemigrations --check --dry-run` passes
   - [ ] `sqlmigrate <app> <migration>` output reviewed (no unexpected DDL)
   - [ ] RLS policy migration paired with model change (if `tenant_id` column added)
   - [ ] Backfill `RunPython` is reversible (`reverse_code` provided)
   - [ ] Index created concurrently for tables >100K rows
   - [ ] `NOT NULL` columns have default + backfill (if existing table)

3. **Required approvers**:
   - 1 platform engineer (for all migrations)
   - 1 DBA/SRE (for migrations touching >1M row tables or adding unique constraints)

## Rollback Procedure

### Safe rollback (no data loss):
```bash
python manage.py migrate <app> <previous_migration>
```

### Unsafe rollback (requires data restore):
1. Stop all application pods (`kubectl scale deploy hub-api --replicas=0`)
2. Restore DB from pre-migration backup (`scripts/backup-postgres.sh restore <timestamp>`)
3. Run migrations to previous state
4. Scale application pods back up

## Emergency Migration Process

For SEV1 incidents requiring immediate schema changes:

1. Engineering Lead + 1 platform engineer approve via Slack (`#incident-p0`)
2. Run migration on staging first — verify in <5 min
3. Run on production — post `#incident-p0` with before/after state
4. File retrospective migration PR within 24h (post-mortem review)
5. Post-mortem documents why emergency process was needed and what preventive measures are added

## CI Enforcement

- `scripts/lint_rls_policies.py` — every new model with `tenant_id` must have paired RLS migration
- `scripts/check_migration_count.py` — fail if any app >200 migrations (squash required)
- `python manage.py makemigrations --check --dry-run` — fail if uncommitted migrations detected

## Data Rehearsal + Data-Loss Veto (Phase U.7)

Before the internal beta cohort is invited (and before any release
promotion), the migration rehearsal SHALL pass on a dedicated disposable
database seeded ONLY with synthetic data (E2E provisioners) — never raw
production data, never the beta staging database itself.

**Runner**: `bash infrastructure/scripts/migration-rehearsal.sh`
(dry-run: `--dry-run`; Makefile: `make rehearsal-migration` with per-op
`APPROVALS="--approve-data-loss <app>.<migration> ..."`).

**Stages**: create disposable DB → full forward migrate from zero →
synthetic dataset via the E2E provisioners (`seed_default_plans`,
`ensure_e2e_user_roles`, `ensure_e2e_subscription`, `init_tenant_configs`,
`ensure_user_tenant_memberships`) → data-loss veto drill per discovered
`DeleteModel` (insert sentinel rows at the predecessor, apply the drop,
prove the rows are destroyed, reverse, re-apply) → idempotence
(`makemigrations --check` + `migrate --check` exit 0) → cleanup.

**The veto**: every `migrations.DeleteModel` op is DISCOVERED from the tree
(`infrastructure/scripts/discover_delete_models.py` — never a hardcoded
count; a new DeleteModel cannot slip past unexamined). An op without an
explicit `--approve-data-loss <app>.<migration>` BLOCKS the rehearsal
(exit 3) and the go/no-go (U.8) reads it as NO-GO. Approve an op ONLY
after recording its justification below. A PERMANENT drop additionally
requires machine-verified proof that no runtime reader/writer of the
table remains (enforced by the rehearsal contract suite,
`make test-rehearsal-migration`).

### Recorded approvals (rehearsal passed 2026-09-03)

| Op | Table | Fate | Justification |
|----|-------|------|---------------|
| `core.0005_remove_eventoutbox_event_outbox_status_created_idx_and_more` | `event_outbox` | permanent drop | Superseded by the `Event` store + write-behind buffer (Phase 313). Legacy DB-backed outbox (`OutboxPublisher`/`process_event_outbox` command) retired with the table — no runtime reader/writer remains (machine-checked). Reprocessing is covered by `replay_events` against `events_event`. |
| `tenants.0097_fix_notification_opt_outs_on_tenant` | `limit_dimensions` | drop + recreate (`0104_limitdimension_and_more`) | Old limit-dimension schema replaced by the Phase-313 limits model; recreated empty by 0104 and repopulated from defaults/`backfill_enterprise_limits`. |
| `scheduled_ingestion.0005_remove_ingestiontemplate_ingestion_te_tenant__idx_and_more` | `ingestion_templates` | drop + recreate (`0010_recreate_ingestion_templates`) | Old template schema replaced by the new template model; templates are rebuildable configuration (system templates re-seeded). |

**Contract suites**: `make test-rehearsal-migration` (discovery-driven veto,
stage order, E2E-provisioner dataset, dangling-reference pin) and
`make test-rehearsal-helm` (lint + full-chart renders + the
semantic/dq/datacontract production path) — both wired into
`test-infra-staging-pipeline` and the CI `infra-staging-scripts` job.
