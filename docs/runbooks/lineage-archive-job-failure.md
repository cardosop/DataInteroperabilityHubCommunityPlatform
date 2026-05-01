# Lineage archive job — failure runbook

**Phase:** 228 F5 (228.F5.19)
**Owner:** Data Platform Eng + SRE
**Last reviewed:** 2026-05-01

This runbook covers two failure modes of the lineage archival
pipeline (228.F5.6):

1. **Hot-tier move stalled** — `archive_lineage_edges` (default
   target=archive) raises mid-run; some rows moved, others didn't.
2. **S3 export stalled** — `archive_lineage_edges --target=s3`
   raises mid-bundle; archive rows are flagged `exported_to_s3_at`
   for some bundles and unflagged for others.

The command is **transactional per batch**, so a partial failure
leaves the database consistent (no half-moved row). The two
recovery paths below apply to the *resumption* of the work that
hadn't yet committed.

## Detect

Page on either signal:

- `lineage_archive_stage_duration_seconds{stage="archive"}` > 30 min
  (Prometheus, scraped by the dlq-depth scrape job).
- The cron container's last `archive_lineage_edges` run exited
  non-zero (`kubectl get cronjob lineage-archive -n hub-staging
  -o json | jq '.status'`).
- The `LineageEdgeArchive.exported_to_s3_at` distribution skews
  ("there's a chunk of rows from > 30 days ago that never made it
  to S3").

## Triage

```bash
# Confirm the cron's last status.
kubectl logs -n hub-staging cronjob/lineage-archive --tail=200

# Capacity sanity:
kubectl exec -n hub-staging deploy/api -- \
    python scripts/lineage_history_growth.py
# Expect invariant_ok=true. If false, a previous archival run
# was incomplete and the hot table is now > 1.5x the open-edge
# state — keep going.
```

## Recover — hot-tier move

```bash
# Re-run with --dry-run first to count remaining candidates.
kubectl exec -n hub-staging deploy/api -- python manage.py \
    archive_lineage_edges \
    --before=$(date -d '12 months ago' +%Y-%m-%d) \
    --dry-run

# Apply if the candidate count is reasonable (< 1M rows):
kubectl exec -n hub-staging deploy/api -- python manage.py \
    archive_lineage_edges \
    --before=$(date -d '12 months ago' +%Y-%m-%d) \
    --batch-size=500
```

The command is idempotent (open edges are NEVER archived; closed
edges already moved to `LineageEdgeArchive` are NOT re-moved
because their `LineageEdge` row is gone).

## Recover — S3 export

```bash
# How many archive rows are still un-exported?
kubectl exec -n hub-staging deploy/api -- python manage.py shell -c "
from hub.apps.contracts.models import LineageEdgeArchive
print(LineageEdgeArchive.objects.filter(exported_to_s3_at__isnull=True).count())
"

# Drive an export run.
kubectl exec -n hub-staging deploy/api -- python manage.py \
    archive_lineage_edges \
    --before=$(date -d '24 months ago' +%Y-%m-%d) \
    --target=s3
```

## Validate

```bash
# Spot-check a recent S3 bundle.
LATEST=$(aws s3 ls s3://meshant-staging-lineage-archive/ --recursive | tail -1 | awk '{print $4}')
aws s3 cp "s3://meshant-staging-lineage-archive/$LATEST" /tmp/x.jsonl.gz
gunzip -c /tmp/x.jsonl.gz | head -3 | jq .

# Re-run the capacity script.
kubectl exec -n hub-staging deploy/api -- \
    python scripts/lineage_history_growth.py
# Expect invariant_ok=true now.
```

## If stuck

If the hot-tier move keeps failing on the same batch:

1. Capture the offending IDs:
   ```bash
   kubectl exec -n hub-staging deploy/api -- python manage.py shell -c "
   from hub.apps.contracts.models import LineageEdge
   for row in LineageEdge.objects.filter(valid_to__lt='2025-05-01').order_by('valid_to')[:10]:
       print(row.id, row.tenant_id, row.edge_type, row.valid_to)
   "
   ```
2. Inspect for malformed timestamps / dangling FK references
   (Postgres treats `valid_to <= NOW() - 100y` differently on
   timezone boundaries).
3. Fix at root cause (reset the row's `valid_to` to a sane value
   via a one-shot SQL migration, then re-run the command).

If the S3 export keeps failing on the same bundle: the bucket
policy may have drifted. Re-apply the Terraform module:

```bash
gh workflow run terraform.yml \
    -f env=staging \
    -f component=lineage_archive
```

## Related

- [Cost forecast](../capacity/lineage-cost-12mo.md)
- [Capacity script](../../scripts/lineage_history_growth.py)
- [Archive command source](../../hub/apps/contracts/management/commands/archive_lineage_edges.py)
- [PITR + RTO/RPO doc](./lineage-pitr-rto-rpo.md)
