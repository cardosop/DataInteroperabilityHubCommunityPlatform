# RB-DATA-001 — Scheduled Ingestion Failure

**Owner:** data-plane-eng@meshant.com | **Created:** 2026-05-18

## 1. Overview
Scheduled ingestion pulls data from external sources (S3, GCS, HTTP, databases) into Hub datasets on a recurring schedule via Prefect workers and dlt pipelines.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| Ingestion run stuck in RUNNING >1h | Worker crash; credential expired; source unreachable |
| All ingestions for tenant failing | `credential_ref` invalid; AWS SM secret rotated |
| Ingested files have 0 rows | Source empty; format mismatch; incremental cursor reset |
| dataset.format field mismatch | Schema inference failed; `_infer_format_from_path` wrong |

## 3. Investigation
1. `python manage.py detect_stuck_runs --direction=ingestion --timeout-hours=1`
2. Check source connectivity: `curl -I <source_url>` or AWS CLI `aws s3 ls`
3. Verify credentials: `resolve_credentials(credential_ref)` in Django shell
4. Check Prefect worker logs: `kubectl logs -l app=hub-worker | grep ingestion`

## 4. Remediation
- **Credential issue:** Update `credential_ref` on `ScheduledIngestion`; rotate SM secret
- **Format mismatch:** Update `source_config.format` or fix `_infer_format_from_path()`
- **Stuck run:** `detect_stuck_runs --execute` to mark FAILED and allow re-run

## 5. Recovery
1. Fix root cause (credential/source/format)
2. Re-enqueue: `ScheduledIngestion.objects.get(id=...).enqueue_run()`
3. Monitor next run: verify COMPLETED within expected window
4. Audit: `SCHEDULED_INGESTION_RUN_COMPLETED` event

## 6. dlt Migration Path (Phase 285.6)

Scheduled ingestions migrated from legacy Prefect-only pipelines to the
**dlt unified engine** (`data_movement_enabled` flag, Phase 285.6). The
migration path:

| Component | Legacy | dlt (Current) |
|---|---|---|
| Pipeline framework | Prefect flows (hub-flows/) | dlt pipelines (hub/data_movement/) |
| Source connectors | Custom Python connectors | dlt verified sources + custom dlt resources |
| Destination | Direct DB writes | dlt destinations (Snowflake, BQ, Postgres) |
| Schema management | Manual schema inference | dlt schema evolution + normalizer |
| Credential management | env vars / AWS SM directly | dlt secrets via `credential_ref` → AWS SM |

**Migration symptoms to watch for:**
- `source_config.format` mismatch after dlt migration → dlt normalizer may infer different types
- `credential_ref` resolution fails → dlt expects secrets in `dlt.secrets` TOML format; bridge layer in `dlt_resources.py` handles AWS SM translation
- Incremental cursor reset → dlt `incremental` column state stored differently; first run after migration may perform full refresh

**Rollback to legacy path:**
```bash
# Disable dlt engine per tenant
PATCH /api/v1/admin/tenants/{id}/feature-flags/ {"data_movement_enabled": false}
# Re-run ingestion with legacy Prefect flow
```

See [`RB-DM-001-dlt-pipeline-failure.md`](RB-DM-001-dlt-pipeline-failure.md) for
dlt-specific pipeline failure investigation.

## 7. Escalation
- **P3:** Single ingestion failure (source-specific)
- **P2:** All ingestions for a tenant failing (credential/config)
- **P1:** Prefect worker down — all ingestions failing
- **Contact:** data-plane-eng@meshant.com, #data-eng Slack

## 7. Related
- `docs/runbooks/RB-DM-001-dlt-pipeline-failure.md`
- `docs/runbooks/RB-DM-002-credential-ref-rotation.md`
- `hub/data_movement/dlt_resources.py`
