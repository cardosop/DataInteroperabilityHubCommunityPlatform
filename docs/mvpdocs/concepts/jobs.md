# Jobs

A job in Meshant represents an asynchronous task execution. Jobs are the universal execution wrapper for any operation that takes more than a few seconds: [DQ runs](dq-runs.md), [compliance scans](compliance-runs.md), dataset processing, exports, transformations, and [orchestration](orchestration.md) workflows. Every long-running operation in the platform creates a job record, providing a consistent interface for tracking progress, handling retries, and managing cancellation.

Jobs are scoped to a [tenant](tenants.md) and created by a [user](users-and-roles.md) or service account. They run on the platform's managed compute pool and are subject to tenant-level concurrency limits and timeout policies.

## Lifecycle

| State | Description |
|---|---|
| `PENDING` | The job is queued and waiting for compute resources. Position in queue is available. |
| `RUNNING` | The job is actively executing. Progress percentage and status messages are updated periodically. |
| `SUCCEEDED` | The job completed without infrastructure errors. Results are available at the job's output location. |
| `FAILED` | The job encountered an error. The error message, stack trace, and partial outputs (if any) are stored. |
| `CANCELLED` | The job was cancelled by a user or by the system (timeout, tenant suspension). Partial results may be available. |
| `RETRYING` | A failed job is being automatically retried based on the retry policy. The retry count and next attempt time are visible. |

Jobs transition from `PENDING` to `RUNNING` when compute resources are allocated. From `RUNNING`, the job moves to `SUCCEEDED`, `FAILED`, or `CANCELLED`. A `FAILED` job may transition to `RETRYING` if automatic retries are configured, and from `RETRYING` back to `RUNNING`.

## Job Types

| Type | Backing Operation |
|---|---|
| `dq_run` | Data quality check execution. See [DQ Runs](dq-runs.md). |
| `compliance_scan` | Compliance and PII scanning. See [Compliance Runs](compliance-runs.md). |
| `dataset_processing` | Post-upload processing: checksum, schema inference, sampling. See [Datasets](datasets.md). |
| `export` | Data export to external storage (S3, GCS, Azure Blob). |
| `transformation` | Data transformation pipeline execution. Creates [lineage](lineage.md) edges. |
| `orchestration` | Multi-step workflow execution. See [Orchestration](orchestration.md). |

## Retry Policy

Jobs support configurable retry behavior:

| Setting | Default | Description |
|---|---|---|
| `max_retries` | 3 | Maximum number of automatic retry attempts. |
| `backoff_strategy` | `exponential` | Delay calculation: `exponential` (2^n minutes) or `fixed` (constant delay). |
| `retry_on` | `infrastructure` | Which failure types trigger retries: `infrastructure` (system errors only) or `all` (including data errors). |

Retries preserve the original job ID. Each attempt increments the `attempt_number` field and records the error from the previous attempt.

## Relationships

- **DQ Runs** -- Every [DQ run](dq-runs.md) is backed by a job. The DQ run ID and the job ID are cross-referenced.
- **Compliance Runs** -- Every [compliance run](compliance-runs.md) is backed by a job.
- **Datasets** -- [Dataset](datasets.md) upload processing creates a job for checksum computation and schema inference.
- **Orchestration** -- [Orchestration](orchestration.md) workflows create a parent job with child jobs for each step.
- **Lineage** -- Transformation jobs create [lineage](lineage.md) edges connecting input assets to output assets.
- **Assets** -- Jobs operate on [assets](assets.md). The asset transitions to `validating` when a DQ or compliance job starts.
- **Webhooks** -- The `job.completed` event fires when any job finishes, delivering the status and summary to configured [webhook](webhooks.md) endpoints.
- **Audit Events** -- Job creation, state transitions, and completions are recorded as [audit events](audit-events.md).

## MVP Scope

**Available at launch:**

- Job creation for DQ runs, compliance scans, and dataset processing.
- Real-time progress tracking (percentage, status message).
- Job listing with filtering by type, state, and date range.
- Cancellation of pending and running jobs.
- Automatic retry with exponential backoff.
- Job timeout enforcement (configurable per tenant, default 1 hour).
- Tenant-level concurrency limits (default 10 concurrent jobs).
- Webhook notification on job completion.

**Post-MVP:**

- Job prioritization (high, normal, low) with priority queuing.
- Job scheduling (cron-based recurring jobs).
- Resource allocation hints (memory, CPU requirements per job type).
- Job cost estimation before execution.
- Cross-tenant job metrics for platform-admin capacity planning.
- Job templates for common operation patterns.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Get job | `GET /api/v1/jobs/{id}` | `meshant job get <id>` | `client.jobs.get(id)` |
| List jobs | `GET /api/v1/jobs` | `meshant job list` | `client.jobs.list()` |
| Cancel job | `POST /api/v1/jobs/{id}/cancel` | `meshant job cancel <id>` | `client.jobs.cancel(id)` |
| Retry job | `POST /api/v1/jobs/{id}/retry` | `meshant job retry <id>` | `client.jobs.retry(id)` |
| Get job logs | `GET /api/v1/jobs/{id}/logs` | `meshant job logs <id>` | `client.jobs.logs(id)` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for filtering options and retry configuration.
