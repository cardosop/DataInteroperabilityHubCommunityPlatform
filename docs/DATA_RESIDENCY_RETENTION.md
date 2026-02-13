# Data Residency and Retention

This document describes where platform data is stored and the retention/delete policy for audit events, dead letter queue (DLQ), and job history. It supports compliance and operational planning.

## Where data is stored

| Data | Storage | Location / table |
|------|---------|-------------------|
| **Audit events** | PostgreSQL | `audit_events` (hub audit app) |
| **Event bus events** | PostgreSQL | `events` (core app); Redis for pub/sub (ephemeral) |
| **Dead letter queue (event bus)** | PostgreSQL | `dead_letter_queue` (core app) |
| **Scheduled ingestion DLQ** | PostgreSQL | `scheduled_ingestion_dlq` (scheduled_ingestion app) |
| **Webhook delivery status** | PostgreSQL | Webhook app models (e.g. delivery records) |
| **Job records** | PostgreSQL | `jobs_job` (jobs app) — job metadata and status |
| **RQ job payloads / results** | Redis | RQ queues (configurable TTL; see Redis configuration) |
| **Workflow execution state** | PostgreSQL | Orchestration app models |
| **File objects** | MinIO (S3-compatible) | Buckets per tenant/use case |
| **Cache** | Redis | Separate instances for cache, queue, events, channels |

**Region / residency**: Storage is in the same region as the deployment (e.g. Docker Compose or Kubernetes cluster). For multi-region or sovereign-cloud requirements, configure deployment and backing stores accordingly; no automatic cross-region replication is described here.

## Audit events

- **Storage**: PostgreSQL table `audit_events`.
- **Immutability**: Audit events are append-only; updates and deletes are disallowed in application code.
- **Retention**: Managed by the `archive_old_audit_events` management command (`hub.apps.audit.management.commands.archive_old_audit_events`). It identifies events older than a configurable retention window (e.g. `--retention_years`). In the current MVP implementation, the command does not delete events; it reports what would be archived. Production implementation is expected to move old events to cold storage or mark as archived; actual deletion (if ever required by policy) would be a separate, controlled process.
- **Delete policy**: No routine delete in application. Any purge or export-for-deletion would require an explicit, compliance-approved process (future work).

## Dead letter queue (DLQ)

- **Event bus DLQ**: PostgreSQL table `dead_letter_queue`. Failed events after max retries are stored here. No automatic retention or purge is implemented; entries are resolved manually (e.g. via admin or API) or left for review.
- **Scheduled ingestion DLQ**: PostgreSQL table `scheduled_ingestion_dlq`. Failed file ingestions are tracked here; retry and resolve are supported via API. No automatic retention/delete policy is implemented.
- **Future work**: Define and implement retention and purge policy (e.g. age-based archive or delete after resolution) for both DLQs to meet compliance and operational needs.

## Job history

- **Job records**: PostgreSQL table `jobs_job` stores job metadata and status (resource type, resource id, status, timestamps, etc.). There is no automatic retention or purge; history accumulates.
- **RQ**: Redis holds RQ job payloads and results; retention is governed by Redis and RQ configuration (e.g. result TTL). Not covered in this doc; see Redis/RQ documentation.
- **Future work**: Define and implement retention or archival for old job records (e.g. by age or status) if required by compliance or operations.

## Summary

| Area | Current state | Future work |
|------|----------------|-------------|
| Audit events | Stored in PostgreSQL; immutable; archive command exists (no delete in app) | Define cold storage/archival and any purge process |
| Event bus DLQ | Stored in PostgreSQL; no auto retention | Define retention and purge policy |
| Scheduled ingestion DLQ | Stored in PostgreSQL; no auto retention | Define retention and purge policy |
| Job history | Stored in PostgreSQL; no auto retention | Define retention/archival if required |

For compliance-specific requirements (e.g. right to erasure, maximum retention, or geographic residency), extend this document and implement the corresponding retention, archival, and delete procedures.
