# Real Scheduled Ingestion and Export E2E Runbook

This runbook describes how to run **real end-to-end** scheduled ingestion and scheduled export flows using **real credentials and storage**. It is intended for **manual or environment-gated** runs only. **No credentials must be stored in the repository.**

## Purpose and scope

- **Goal:** Validate scheduled ingestion sources (S3, GCS, AZURE_BLOB, HTTP/HTTPS, FTP/SFTP, DATABASE) and scheduled export destinations (S3, GCS, AZURE_BLOB) with real provider credentials and real data transfer; document steps to run one successful real E2E run per connector type (or a documented skip reason).
- **Out of scope:** Automated CI with secrets; mock or stub credentials.
- **References:**
  - [Scheduled Export Guide](../SCHEDULED_EXPORT_GUIDE.md) — destination config, credentials, execution model
  - [Scheduled Ingestion Worker API](../SCHEDULED_INGESTION_WORKER_API.md) — internal endpoints, worker auth
  - [Prefect Integration Service](../../services/prefect-integration/README.md) — source connectors, worker env
  - [Services Architecture](../SERVICES_ARCHITECTURE.md) — Prefect worker → Hub API flow

## Prerequisites

- Hub API running (e.g. `docker compose up -d`; API base URL known, e.g. `http://localhost:8000`).
- Prefect server and Prefect worker running (e.g. `prefect-server`, `prefect-worker` in Docker Compose).
- Prefect Integration Service running (for deployment sync and triggers).
- Authenticated user with permissions to create/manage scheduled ingestions and scheduled exports (e.g. DATA_PRODUCT_OWNER, TENANT_ADMIN).
- Tenant context for the authenticated user.
- **Worker API keys** (never committed):
  - `HUB_WORKER_API_KEY` — scope `scheduled_ingestion:internal` for ingestion worker
  - `HUB_WORKER_API_KEY` — scope `scheduled_export:internal` for export worker (can be same key if scopes include both)
  - Generate via: `python hub/manage.py create_api_key --scopes scheduled_ingestion:internal scheduled_export:internal`
- Real provider credentials available **only via environment variables or Prefect Blocks** (never committed).

## Connector support summary

| Direction   | Connector   | Config / credentials |
|------------|-------------|----------------------|
| **Ingestion sources** | S3 | `bucket`, `prefix`, `access_key_id`, `secret_access_key`, `endpoint_url`, `region`; env: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` or Prefect Blocks |
| | GCS | `bucket`, `prefix`, `credentials_json`, `project`; env: `GOOGLE_APPLICATION_CREDENTIALS` or Prefect Blocks |
| | AZURE_BLOB | `account_name`, `account_key`, `container`, `prefix`; env: `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_ACCOUNT_KEY` or Prefect Blocks |
| | HTTP / HTTPS | `base_url`, `paths`, `auth`, `headers` |
| | FTP / SFTP | `host`, `port`, `username`, `password`, `protocol`, `path`, `key_file` |
| | DATABASE | `type`, `host`, `port`, `database`, `username`, `password`, `schema`, `tables` |
| **Export destinations** | S3 | `bucket`, `prefix`, `access_key_id`, `secret_access_key`, `region`; env: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` or Prefect Blocks |
| | GCS | `bucket`, `prefix`, `service_account_key`; env: `GOOGLE_APPLICATION_CREDENTIALS` or Prefect Blocks |
| | AZURE_BLOB | `container`, `prefix`, `account_name`, `account_key`; env: `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_ACCOUNT_KEY` or Prefect Blocks |

Credentials in hub config are masked in API responses (`***masked***`). Workers can resolve credentials from Prefect Blocks or from environment variables at runtime.

---

## Environment variables (worker and runbook)

Set these **only in the environment** (or in Prefect Blocks); never commit.

### Prefect worker (ingestion and export)

| Variable | Purpose |
|----------|--------|
| `PREFECT_API_URL` | Prefect API URL (e.g. `http://prefect-server:4200/api`) |
| `PREFECT_API_KEY` | Optional; required if Prefect server uses API key auth |
| `HUB_BASE_URL` | Hub API base URL (e.g. `http://api-service:8000`) |
| `HUB_WORKER_API_KEY` | API key with `scheduled_ingestion:internal` and/or `scheduled_export:internal` |

### S3 (ingestion source or export destination)

| Variable | Purpose |
|----------|--------|
| `AWS_ACCESS_KEY_ID` | AWS access key (alternative to storing in config/Blocks) |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_DEFAULT_REGION` | Optional; default region (e.g. `us-east-1`) |

### GCS (ingestion source or export destination)

| Variable | Purpose |
|----------|--------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCS service account JSON file (alternative to embedding in config/Blocks) |

### Azure Blob (ingestion source or export destination)

| Variable | Purpose |
|----------|--------|
| `AZURE_STORAGE_ACCOUNT_NAME` | Storage account name |
| `AZURE_STORAGE_ACCOUNT_KEY` | Storage account key |

### Optional: real E2E test entrypoint

| Variable | Purpose |
|----------|--------|
| `REAL_SCHEDULED_E2E` | Set to `1` to allow running pytest tests marked `real_scheduled_e2e`; these tests use real storage/credentials per this runbook and use **no mocks**. When unset, such tests are skipped. |

See [Optional: env-gated real E2E tests](#optional-env-gated-real-e2e-tests) below.

---

## Prefect Blocks (recommended for credentials)

Store credentials in Prefect Blocks so hub config can reference them and workers resolve at runtime without putting secrets in the hub database.

### S3 Block (ingestion or export)

```python
from prefect_aws import S3Bucket

s3_bucket = S3Bucket(
    bucket_name="my-bucket",
    aws_access_key_id="AKIA...",
    aws_secret_access_key="..."
)
s3_bucket.save("my-s3-block")
```

Reference the block in hub config by block name; worker resolves credentials from Prefect when executing.

### GCS / Azure

Use the appropriate Prefect block type for GCS or Azure Blob and save with a unique name. Configure the hub scheduled ingestion/export with the block reference (or rely on env vars in the worker).

**Note:** Hub API may accept credentials in `source_config` / `destination_config`; those values are masked in responses. For real E2E, prefer Prefect Blocks or worker env vars so secrets never touch the hub DB in plaintext.

---

## Steps to run a real scheduled ingestion

1. **Set worker env** (and optionally source credentials via env or Prefect Blocks):
   - `PREFECT_API_URL`, `HUB_BASE_URL`, `HUB_WORKER_API_KEY`
   - For S3: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (or configure Block)
   - For GCS: `GOOGLE_APPLICATION_CREDENTIALS` (or Block)
   - For Azure: `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_ACCOUNT_KEY` (or Block)
   - For FTP/SFTP/DATABASE: provide credentials via config (masked) or via Blocks if supported

2. **Create a scheduled ingestion** via API (or UI):
   - `POST /api/v1/scheduled-ingestions/`
   - Body: `name`, `source_type` (e.g. `S3`, `GCS`, `AZURE_BLOB`, `HTTP`, `HTTPS`, `FTP`, `SFTP`, `DATABASE`), `source_config` (bucket/container/url/path, etc.; credentials can be omitted if using Blocks/env), `schedule_config` (e.g. `{"cron": "0 2 * * *"}`), `file_pattern`, tenant context.

3. **Sync Prefect deployment** (if not automatic): ensure the Prefect Integration Service has synced the deployment for this scheduled ingestion (e.g. `POST .../deployments/sync` or equivalent).

4. **Trigger a run** (one-off for testing):
   - `POST /api/v1/scheduled-ingestions/{id}/trigger/`
   - Or wait for the cron schedule.

5. **Verify:** Poll run status:
   - `GET /api/v1/scheduled-ingestions/{id}/runs/` — confirm a run in `COMPLETED` (or inspect `FAILED` and check Prefect flow logs).
   - In Prefect UI: find the flow run by `prefect_flow_run_id` / run ID; check logs for discovery and file processing.
   - In Hub: verify assets/datasets/files created as expected for the source.

---

## Steps to run a real scheduled export

1. **Set worker env** (and optionally destination credentials via env or Prefect Blocks):
   - `PREFECT_API_URL`, `HUB_BASE_URL`, `HUB_WORKER_API_KEY`
   - For S3: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (or Block)
   - For GCS: `GOOGLE_APPLICATION_CREDENTIALS` (or Block)
   - For Azure: `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_ACCOUNT_KEY` (or Block)

2. **Create a scheduled export** via API (or UI):
   - `POST /api/v1/scheduled-exports/`
   - Body: `name`, `schedule_config` (e.g. `{"cron": "0 2 * * *"}`), `destination_type` (`S3`, `GCS`, or `AZURE_BLOB`), `destination_config` (bucket/container, prefix; credentials omitted if using env/Blocks), `source_scope` (e.g. `asset_ids`, `dataset_ids`, `file_ids`, or `contract_id`).

3. **Trigger a run** (one-off for testing):
   - `POST /api/v1/scheduled-exports/{id}/trigger/`

4. **Verify:** Poll run status:
   - `GET /api/v1/scheduled-exports/{id}/runs/` — confirm a run in `COMPLETED` (or inspect failure and Prefect flow logs).
   - In the destination bucket/container: verify objects written as expected.

See [Scheduled Export Guide](../SCHEDULED_EXPORT_GUIDE.md) for destination config shapes, rate limiting, and troubleshooting (stuck runs, failed runs, Prefect unavailable).

---

## Optional: env-gated real E2E tests

Tests that perform **real data transfer** against real storage/credentials (no mocks) are marked with the pytest marker **`real_scheduled_e2e`**. They run **only when** the environment variable **`REAL_SCHEDULED_E2E=1`** is set; otherwise they are skipped.

- **Rationale:** Avoid running real transfer tests in CI or default local runs; allow explicit opt-in for validation per this runbook.
- **No mocks:** When `REAL_SCHEDULED_E2E=1` is set, those tests use real credentials and real storage as documented in this runbook.

### How to run

1. Set credentials and worker env as in the sections above (or use test buckets/containers with minimal data).
2. Set the guard:
   ```bash
   export REAL_SCHEDULED_E2E=1
   ```
3. Run the real E2E tests:
   ```bash
   pytest -m real_scheduled_e2e -v
   ```
   Or from project root with Django settings:
   ```bash
   DJANGO_SETTINGS_MODULE=hub.settings REAL_SCHEDULED_E2E=1 pytest hub/apps tests -m real_scheduled_e2e -v
   ```

4. To **exclude** these tests from a normal run (e.g. CI):
   ```bash
   pytest -m 'not real_scheduled_e2e'
   ```

The marker is registered in the project `pytest.ini`; see root `pytest.ini` for the full marker list.

---

## Troubleshooting

- **Worker 401/403:** Check `HUB_WORKER_API_KEY` and `X-Tenant-ID`; ensure the key has `scheduled_ingestion:internal` and/or `scheduled_export:internal`.
- **Prefect 503:** Ensure Prefect server and worker are running; see [SCHEDULED_EXPORT_GUIDE](../SCHEDULED_EXPORT_GUIDE.md#prefect-service-unavailable).
- **Source/destination connection failures:** Verify credentials (env or Prefect Blocks); check bucket/container names and regions; for DATABASE/FTP/SFTP check network and credentials.
- **Stuck or failed runs:** Correlate hub run ID with Prefect flow run ID; check Prefect flow logs and hub internal API responses; see [SCHEDULED_EXPORT_GUIDE](../SCHEDULED_EXPORT_GUIDE.md#troubleshooting).

---

**Last updated:** 2026-02-20  
**Version:** 1.0.0
