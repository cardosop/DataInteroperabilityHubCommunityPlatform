# Scheduled Export Guide

**Last Updated**: 2026-02-03
**Version**: 1.0.0

---

## Overview

Scheduled Export enables recurring export of hub datasets/files to external destinations such as S3, GCS, and Azure Blob Storage. Exports are executed by Prefect workers for reliability and scalability.

**Key Capabilities**:
- Configure recurring exports with cron schedules
- Export to S3, GCS, or Azure Blob Storage
- Define source scope by assets, datasets, files, or contracts
- Monitor export runs with status and counts
- Manually trigger one-off exports
- View run history and troubleshoot failures

---

## Table of Contents

1. [Configuration](#configuration)
2. [Execution Model](#execution-model)
3. [Destination Connectors](#destination-connectors)
4. [Credentials Management](#credentials-management)
5. [Runbook Links](#runbook-links)
6. [Troubleshooting](#troubleshooting)
7. [Related Documentation](#related-documentation)

---

## Configuration

### Source Scope

Define what data to export using one or more of these fields:

- **Asset IDs**: Export all datasets/files associated with specific assets
- **Dataset IDs**: Export specific datasets
- **File IDs**: Export specific files
- **Contract ID**: Export data associated with a specific contract

**Validation**: At least one scope field must have non-empty values.

**Example**:
```json
{
  "source_scope": {
    "asset_ids": ["550e8400-e29b-41d4-a716-446655440000"],
    "dataset_ids": [],
    "file_ids": [],
    "contract_id": null
  }
}
```

### Destination Configuration

Configure export destination:

**S3**:
```json
{
  "destination_type": "S3",
  "destination_config": {
    "bucket": "my-export-bucket",
    "prefix": "exports/sales/",
    "access_key_id": "AKIA...",
    "secret_access_key": "..."
  }
}
```

**GCS**:
```json
{
  "destination_type": "GCS",
  "destination_config": {
    "bucket": "my-export-bucket",
    "prefix": "exports/sales/",
    "service_account_key": "..."
  }
}
```

**Azure Blob**:
```json
{
  "destination_type": "AZURE_BLOB",
  "destination_config": {
    "container": "exports",
    "prefix": "sales/",
    "account_name": "mystorageaccount",
    "account_key": "..."
  }
}
```

### Schedule Configuration

Define export schedule using cron expressions:

**Example**:
```json
{
  "schedule_config": {
    "cron": "0 2 * * *"  // Daily at 2 AM UTC
  }
}
```

**Common Cron Patterns**:
- `0 2 * * *` - Daily at 2 AM UTC
- `0 */6 * * *` - Every 6 hours
- `0 0 * * 0` - Weekly on Sunday at midnight
- `0 0 1 * *` - Monthly on the 1st at midnight

---

## Execution Model

### Prefect Worker → Hub API

Scheduled exports are executed by **Prefect workers** that communicate with the Hub API via internal endpoints:

1. **Prefect Scheduler**: Triggers flow runs based on cron schedule
2. **Prefect Worker**: Executes `scheduled_export_full_flow` (HTTP-only, no Django)
3. **Hub API**: Provides internal endpoints for:
   - Run lifecycle management (`POST /api/v1/scheduled-exports/internal/runs/`, `PATCH /api/v1/scheduled-exports/internal/runs/{id}/`)
   - Export processing (`POST /api/v1/scheduled-exports/internal/process-export/`)
   - Configuration retrieval (`GET /api/v1/scheduled-exports/internal/config/{id}/`)

### Authentication

**Worker API Key**:
- Environment variable: `HUB_WORKER_API_KEY`
- Database API key: Scope `scheduled_export:internal`
- Header: `Authorization: ApiKey <key>`
- Tenant header: `X-Tenant-ID: <tenant-uuid>` (if using environment-based key)

### Rate Limiting

**Internal Worker API**: No rate limit (internal endpoints excluded from rate limiting)

**Public API**: Standard rate limits apply (see [API Endpoints Reference](API_ENDPOINTS_REFERENCE_SCHEDULED_EXPORT.md#rate-limiting))

### Hub as Source of Truth

- **Configuration**: Stored in Hub database (credentials masked in API responses)
- **State**: Run status, counts, timestamps stored in Hub
- **Prefect**: Executes exports but does not store configuration or state

---

## Destination Connectors

### S3 Connector

**Configuration**:
- `bucket` (required): S3 bucket name
- `prefix` (optional): S3 key prefix
- `access_key_id` (required): AWS access key ID
- `secret_access_key` (required): AWS secret access key
- `region` (optional): AWS region (defaults to us-east-1)

**Credentials**: Configured via Prefect Blocks or environment variables

### GCS Connector

**Configuration**:
- `bucket` (required): GCS bucket name
- `prefix` (optional): GCS object prefix
- `service_account_key` (required): GCS service account JSON key

**Credentials**: Configured via Prefect Blocks or environment variables

### Azure Blob Connector

**Configuration**:
- `container` (required): Azure Blob container name
- `prefix` (optional): Blob prefix
- `account_name` (required): Azure storage account name
- `account_key` (required): Azure storage account key

**Credentials**: Configured via Prefect Blocks or environment variables

---

## Credentials Management

### Prefect Blocks

**Recommended**: Store credentials in Prefect Blocks for secure management:

1. Create Prefect Block for destination credentials
2. Reference block in export configuration
3. Worker retrieves credentials from Prefect at runtime

**Example** (S3 Block):
```python
from prefect_aws import S3Bucket

s3_bucket = S3Bucket(
    bucket_name="my-export-bucket",
    aws_access_key_id="AKIA...",
    aws_secret_access_key="..."
)
s3_bucket.save("my-export-bucket-block")
```

### Environment Variables

**Alternative**: Set credentials as environment variables in Prefect worker:

- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (for S3)
- `GOOGLE_APPLICATION_CREDENTIALS` (for GCS)
- `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_ACCOUNT_KEY` (for Azure Blob)

**Security**: Credentials are masked in Hub API responses (`***masked***`)

---

## Runbook Links

**Real E2E (manual / env-gated):**
- [REAL_SCHEDULED_INGESTION_EXPORT_E2E](../runbooks/REAL_SCHEDULED_INGESTION_EXPORT_E2E.md) — Run real scheduled ingestion and export with real credentials (S3, GCS, Azure Blob, HTTP/FTP/DATABASE); env vars, Prefect Blocks, steps; optional pytest marker `real_scheduled_e2e` (guard `REAL_SCHEDULED_E2E=1`). No credentials in repo.

**Operational Procedures** (when available):
- [RB-SCHEDULED-EXPORT-001](../runbooks/RB-SCHEDULED-EXPORT-001.md) - Scheduled Export Operations (Prefect Worker)
  - Verify Prefect worker and pool
  - Correlate Prefect flow_run_id with hub run_id
  - Restart worker and redeploy flow
  - Handle stuck runs and failed runs

**Related Runbooks**:
- [RB-DEPLOY-001](../runbooks/RB-DEPLOY-001.md) - Standard Deployment Procedure
- [RB-SCHEDULED-INGESTION-001](../runbooks/RB-SCHEDULED-INGESTION-001.md) - Scheduled Ingestion Operations (similar procedures)

---

## Troubleshooting

### Stuck Runs

**Definition**: Run in `RUNNING` status for > 2 hours

**Detection**:
- Prometheus alert: `ScheduledExportRunStuck`
- Database query: `SELECT * FROM scheduled_export_scheduledexportrun WHERE status = 'RUNNING' AND started_at < NOW() - INTERVAL '2 hours';`

**Remediation**:
1. Check Prefect flow run status
2. Determine root cause (Prefect failed but hub still RUNNING, or flow stuck)
3. Update hub run status via internal API or Django shell
4. Cancel Prefect flow run if still running

See [RB-SCHEDULED-EXPORT-001](../runbooks/RB-SCHEDULED-EXPORT-001.md#4-handle-stuck-runs) for detailed procedures.

### Failed Runs

**Common Causes**:
- Authentication failure (worker API key invalid)
- Destination connection failure (credentials invalid)
- Source scope validation failure (no items found or access denied)
- Prefect flow execution failure

**Investigation**:
1. Review run error message
2. Check Prefect flow logs (via Prefect UI)
3. Verify destination credentials
4. Verify source scope is valid and accessible

See [RB-SCHEDULED-EXPORT-001](../runbooks/RB-SCHEDULED-EXPORT-001.md#5-handle-failed-runs) for detailed procedures.

### Prefect Service Unavailable

**Symptoms**:
- Export creation returns 503 Service Unavailable
- Prefect deployment sync fails
- Trigger returns 503

**Remediation**:
1. Verify Prefect server is running
2. Verify Prefect worker is connected
3. Check Prefect API connectivity
4. Retry export creation/trigger after Prefect is available

**Graceful Degradation**: Export creation may succeed even if Prefect sync fails (sync deferred)

### Logs

**Hub API Logs**:
- Check `api-service` logs for export creation/trigger
- Check for authentication errors (401/403)
- Check for validation errors (400)

**Prefect Flow Logs**:
- Access via Prefect UI: Flow Runs → Select run → Logs
- Check for destination connection errors
- Check for source scope access errors

**Worker Logs**:
- Docker Compose: `docker-compose logs prefect-worker`
- Kubernetes: `kubectl logs -l app=prefect-worker -n prefect`

---

## Related Documentation

- **[Features](FEATURES.md#scheduled-export)** - Feature overview and capabilities
- **[Use Cases](USE_CASES.md#scheduled-export-use-cases)** - UC-EXPORT-001–004
- **[User Journeys](USER_JOURNEYS.md#scheduled-export-journeys)** - JOURNEY-EXPORT-001–002
- **[API Reference](API_ENDPOINTS_REFERENCE_SCHEDULED_EXPORT.md)** - Complete API documentation
- **[Services Architecture](SERVICES_ARCHITECTURE.md#scheduled-export-execution-model)** - Execution model details
- **[Runbooks](../runbooks/RB-SCHEDULED-EXPORT-001.md)** - Operational procedures

---

## Quick Reference

### Create Scheduled Export

```bash
curl -X POST http://localhost:8000/api/v1/scheduled-exports/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily Sales Export",
    "schedule_config": {"cron": "0 2 * * *"},
    "destination_type": "S3",
    "destination_config": {
      "bucket": "export-bucket",
      "prefix": "exports/sales/"
    },
    "source_scope": {
      "asset_ids": ["550e8400-e29b-41d4-a716-446655440000"]
    }
  }'
```

### Trigger Export

```bash
curl -X POST http://localhost:8000/api/v1/scheduled-exports/{id}/trigger/ \
  -H "Authorization: Bearer <token>"
```

### List Runs

```bash
curl http://localhost:8000/api/v1/scheduled-exports/{id}/runs/ \
  -H "Authorization: Bearer <token>"
```

---

**Last Updated**: 2026-02-03
**Version**: 1.0.0
