# Monitoring

This page documents the Meshant monitoring stack.

## Stack Overview

| Component        | Purpose                                      |
|------------------|----------------------------------------------|
| Prometheus       | Metrics collection and alerting rules        |
| Grafana          | Dashboards and visualization                 |
| django-structlog | Structured JSON logging from the backend     |
| X-Trace-ID       | Distributed trace correlation across services|

## Metrics

The backend exposes Prometheus metrics at `/metrics/`. Key metrics
include:

- **http_requests_total** -- request count by method, path, status
- **http_request_duration_seconds** -- latency histogram
- **db_query_duration_seconds** -- database query latency
- **celery_task_duration_seconds** -- background task execution time
- **cache_hit_ratio** -- Redis cache hit/miss ratio

## Dashboards

Grafana dashboards are provisioned via Helm. The primary dashboards
cover:

- **Platform Overview** -- request rate, error rate, latency P50/P95/P99
- **Database** -- connection pool usage, slow queries, replication lag
- **Background Tasks** -- Celery queue depth, task success/failure rates
- **Infrastructure** -- pod CPU/memory, node utilization

## Alerting

Prometheus alerting rules fire on conditions such as:

- Error rate above 1% for 5 minutes
- P95 latency above 2 seconds for 5 minutes
- Pod restart count above 3 in 15 minutes
- Database connection pool above 80% utilization
- Disk usage above 85%

Alerts route to the configured notification channels (Slack, PagerDuty).

## Structured Logging

All backend services emit structured JSON logs via `django-structlog`.
Each log entry includes `trace_id`, `tenant_id`, `user_id`, and
`service` fields for filtering.

## Related

- [Health Checks](health-checks.md) -- endpoint monitoring
- [Incident Response](incident-response.md) -- responding to alerts
