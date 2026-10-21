# Runbook: file retention and hard purge (Phase 260.1.A)

## Behaviour

1. **API delete** (`DELETE /api/v1/files/{id}/`) sets `File.status=DELETING`, stamps `deleted_at`, and tags the S3 object with `meshant-file-lifecycle=pending-hard-purge` (best-effort). The blob remains recoverable until the grace window ends.
2. **Hard purge** (`python manage.py purge_deleted_files`) removes eligible objects from storage, deletes the `File` row, and writes an audit row with action `FILE_PURGED` (PII-redacted `details_json` per compliance helpers).
3. **Per-tenant grace** is `Tenant.file_soft_delete_grace_days` (default **30**, bounds **[7, 365]**).

## Operations

### Dry run (recommended first)

```bash
docker compose exec api-service python manage.py purge_deleted_files --dry-run
```

Two consecutive dry runs against the same database should report the **same** candidate counts (idempotent observation).

### Production purge

```bash
docker compose exec api-service python manage.py purge_deleted_files --no-dry-run
```

### D260.10 safety net

If `FILE_PURGE_DRY_RUN_REQUIRED=true` is set in the environment, the command **forces** dry-run unless the operator passes `--no-dry-run` explicitly. Helm sets this when `purgeDeletedFiles.dryRun: true`.

### Distributed lock

The command acquires Redis key `meshant:purge_deleted_files:v1` (SETNX + TTL). Only one purge job should run cluster-wide; if the lock is held, the process exits with status **1**.

### Kubernetes

CronJob: `helm/templates/cronjob/purge-deleted-files.yaml` — default schedule **03:00 UTC**, values block `purgeDeletedFiles` in `helm/values.yaml`.

### Terraform (hub-files bucket)

`infrastructure/terraform/modules/s3-buckets/main.tf`:

- Multipart uploads: **abort after 1 day** (S3 whole-day granularity; satisfies “>24h” safety margin).
- Lifecycle rule: expire objects tagged `meshant-file-lifecycle=pending-hard-purge` after **400** days (safety net if the app never purges).

## Performance (260.1.A.9)

Nightly load scenario: `tests/load/file_purge_retention.k6.js` — documents thresholds (**\<5 min** for 10k files, **\<100 ms** Redis lock wait under nominal conditions). Tune k6 `vus` / duration to match your environment; assert on trend in Grafana + job `activeDeadlineSeconds`.

## Related tests

```bash
pytest hub/apps/files/tests/test_purge_deleted_files.py -q
```

Include Redis in the test stack when exercising the management command.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
