# Data Residency & Retention

## Audit Events
Audit events are stored in the `audit_events` table with tenant-scoped partitioning. Retention is governed by the data classification level of the audited resource and the tenant's plan tier.

## DLQ (Dead Letter Queue)
Failed jobs and undeliverable events are routed to the Dead Letter Queue (DLQ). DLQ entries are retained for 30 days before automatic purge. Operators can replay individual DLQ entries via the `/api/v1/jobs/dlq/` endpoint.

## Job History
Job execution history is retained per-tenant. Completed jobs are retained for 90 days; failed jobs are retained for 30 days. The retention policy is configurable per tenant via `settings.JOB_HISTORY_RETENTION_DAYS`.

## Data Residency
All tenant data (audit, DLQ, job history) is stored in the region specified at tenant creation time. Multi-region replication is available for Enterprise-tier tenants.
