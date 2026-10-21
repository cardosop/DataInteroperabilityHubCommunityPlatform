# Orphan-DRAFT cleanup — runbook

**Phase**: 250.1.E (orphan-DRAFT cleanup sweep)

## Scope

Reclaim DRAFT-status `Asset` rows that have aged past the configured threshold (default 30 days). These are the long-tail of pre-Phase-250.1.A workflow runs that never progressed past `DRAFT`, plus any future runs that abort between `asset_create` and `activate` without compensation deletion.

**Definition of orphan** (mirrors the implemented filter in `hub/apps/assets/management/commands/cleanup_orphan_drafts.py`):

```
Asset.status == DRAFT  AND  Asset.created_at < (now - age_threshold_days)
```

The sweep does NOT consult any `workflow_run_id` linkage — DRAFT + age is sufficient because ACTIVE/PUBLIC/RETIRED rows are never candidates regardless of workflow state.

## Symptoms

- Tenant reports stale DRAFT assets visible in their listing UI.
- Tenant quota approaching cap with assets they never see.
- Grafana shows growing DRAFT count at older percentiles.

## Diagnosis

```
python manage.py shell -c "
from datetime import timedelta
from django.utils import timezone
from hub.apps.assets.models import Asset, AssetStatus
cutoff = timezone.now() - timedelta(days=30)
count = Asset.objects.filter(
    status=AssetStatus.DRAFT,
    created_at__lt=cutoff,
).count()
print(f'Orphan-DRAFT count: {count}')
"
```

## Scheduling

The sweep runs as a Kubernetes CronJob defined at `helm/templates/cronjob/cleanup-orphan-drafts.yaml` — daily at `0 4 * * *` UTC (one hour after `purge-dq-runs` to avoid resource contention).

Concurrency policy is `Forbid`; a long-running prior pass MUST finish before the next one starts.

## Cleanup procedure

1. **Dry-run is the default for 7 days post-deploy** — the Helm chart sets `cleanupOrphanDrafts.dryRun: true` which exposes `ASSET_ORPHAN_CLEANUP_DRY_RUN=1` to the pod env. The command reads that env var and forces `--dry-run` regardless of CLI flag (mirrors D240.16). Pass `--no-dry-run` to override the env var deliberately.

2. **Manual smoke run** for one tenant:
   ```
   python manage.py cleanup_orphan_drafts \
     --dry-run \
     --tenant-id=<uuid> \
     --age-threshold-days=30
   ```
   Output lists `cleanup_orphan_drafts starting:` config banner plus `cleanup_orphan_drafts complete: would delete N orphan DRAFT assets across M tenant(s).` Verify count is plausible.

3. **Audit-trail check**. Each batch (≤500 rows by default) emits one `ASSET_ORPHAN_DRAFT_PURGED` `AuditEvent`. Filter by:
   ```
   python manage.py shell -c "
   from hub.apps.audit.models import AuditEvent
   for e in AuditEvent.objects.filter(action='ASSET_ORPHAN_DRAFT_PURGED').order_by('-timestamp')[:20]:
       d = e.details_json or {}
       print(d.get('correlation_id'), d.get('tenant_id'), d.get('count'), d.get('dry_run'), d.get('batch'))
   "
   ```
   All batches from the same cron-run share one `correlation_id` so you can scope to a single sweep.

4. **Flip dry-run off** after operator review of 7 days of `dry_run: true` audit rows shows zero false-positives:
   ```
   helm upgrade hub ./helm \
     --set cleanupOrphanDrafts.dryRun=false \
     --reuse-values
   ```
   The next CronJob fire will hard-delete (no env var means no override).

5. **Per-tenant one-off** when you need to clean a single tenant outside the daily schedule:
   ```
   kubectl create job --from=cronjob/hub-cleanup-orphan-drafts \
     hub-cleanup-orphan-drafts-manual-$(date +%s) \
     -n hub-staging
   ```
   Or via direct exec into an api pod with `--tenant-id=<uuid>`.

## Audit-event shape

`ASSET_ORPHAN_DRAFT_PURGED` carries the following keys in `details_json`:

| Key | Type | Purpose |
| --- | --- | --- |
| `tenant_id` | str | Tenant scope of this batch |
| `count` | int | Rows in this batch (≤ batch_size) |
| `dry_run` | bool | True if env-var safety net or `--dry-run` flag held |
| `batch` | int | 1-indexed batch number within the tenant |
| `age_threshold_days` | int | Threshold this run used (for replay) |
| `asset_ids` | list[str] | First 10 ids in the batch (sample for triage) |
| `correlation_id` | str | UUID stamped on every batch from one cron-run |

## Hard-delete — no rollback

The sweep performs `Asset.objects.filter(pk__in=batch_ids).delete()` — a hard DELETE, not a soft delete. There is no restore command. Once a row is purged, it is gone.

This is intentional: DRAFT rows that have aged past 30 days have never been published, never been queried by external consumers, and have no downstream lineage. Soft-deletion adds storage cost without buying meaningful recovery semantics for this class of row.

If a customer reports an unexpected purge, the audit trail (`ASSET_ORPHAN_DRAFT_PURGED` + `correlation_id`) gives you the asset_ids, batch number, and tenant scope — but the row itself is unrecoverable from the application DB. The customer must re-create the asset through the Phase 250.1.A workflow.

## Knobs

`helm/values.yaml → cleanupOrphanDrafts`:

| Field | Default | Purpose |
| --- | --- | --- |
| `enabled` | `true` | Disable the entire CronJob |
| `schedule` | `"0 4 * * *"` | Cron expression in pod-local UTC |
| `dryRun` | `true` | Sets `ASSET_ORPHAN_CLEANUP_DRY_RUN=1` env (forces dry-run) |
| `ageThresholdDays` | `""` (→30) | Override the default age threshold |
| `batchSize` | `""` (→500) | Override the default batch size |
| `resources` | 100m/256Mi req, 500m/512Mi limit | Per-batch transaction is short; small footprint sufficient |

## Escalation

- Sweep job stays in CrashLoopBackOff: SRE on-call. Inspect pod logs; check that `ASSET_ORPHAN_CLEANUP_DRY_RUN` env var is set as expected if dry-run is desired.
- Tenant complaint about unexpectedly purged DRAFT: customer-success → Eng. Pull `AuditEvent` rows by `details_json.tenant_id` and `details_json.correlation_id`; the row itself is unrecoverable. If the issue is policy (30 days too aggressive for a tenant), tune `ageThresholdDays` higher.
- Audit emission failures (best-effort try/except in `_emit_purged_audit`): grep pod logs for `cleanup_orphan_drafts_audit_emit_failed`. The sweep continues even if audit insertion fails — losing one audit row is preferred over skipping a batch's deletion.
