# Meshant Service Level Objectives

**Date:** 2026-05-20
**Owner:** Platform Engineering
**Review cadence:** Monthly (first Monday)

## 1. API Availability

| Metric | Target | Window |
|---|---|---|
| Uptime | 99.9% | 30 days rolling |
| 5xx error rate | < 0.1% of all requests | 30 days rolling |
| Health check success rate | 100% | 5 minutes |

**Measurement:** `up{job="api-service"}` Prometheus metric.
**Alert:** `ServiceDown` (critical, P1) — fires when `up == 0` for >1 min.

## 2. API Latency

| Metric | Target | Window |
|---|---|---|
| P50 latency | < 100ms | 5 minutes |
| P95 latency | < 500ms | 5 minutes |
| P99 latency | < 2s | 5 minutes |

**Measurement:** `histogram_quantile(0.95, rate(http_server_request_duration_seconds_bucket[5m]))`
**Alert:** `HighLatency` (warning, P2) — P95 > 500ms for >5 min.

## 3. Job Processing

| Metric | Target | Window |
|---|---|---|
| Job queue depth (critical) | < 10 pending | 5 minutes |
| Job queue depth (default+low) | < 100 pending | 5 minutes |
| Job P95 execution time | < 2x 24h baseline | 30 minutes |
| Job failure rate | < 5% | 1 hour |

**Measurement:** `rq_jobs_total{status="queued"}` per queue.
**Alert:** `HubHeavyQueueBacklog` (critical, P1), `HubLightQueueBacklog` (warning, P2).

## 4. Data Freshness

| Metric | Target | Window |
|---|---|---|
| Scheduled ingestion latency | < 2x configured interval | per ingestion |
| Compliance scan latency | < 30s P95 | 5 minutes |
| DQ run latency | < 5 min P95 | 5 minutes |

**Measurement:** `scheduled_ingestion_duration_seconds` histogram, `compliance_scan_duration_seconds`.

## 5. Database

| Metric | Target | Window |
|---|---|---|
| Connection pool utilization | < 80% | 5 minutes |
| Replication lag | < 10s | 2 minutes |
| PgBouncer client wait P95 | < 30s | 5 minutes |

**Alert:** `DatabaseConnectionPoolExhausted` (critical), `HubReplicationLagHigh` (warning).

## 6. Dependencies

| Dependency | Availability Target | Latency Target |
|---|---|---|
| PostgreSQL | 99.95% | < 10ms P95 |
| Redis (cache) | 99.9% | < 1ms P95 |
| Redis (queue) | 99.9% | < 5ms P95 |
| Fuseki | 99.5% | < 500ms P95 |
| Stripe API | 99.9% (vendor) | < 2s P95 |
| Compliance service | 99.5% | < 5s P95 |
| Prefect API | 99.5% | < 2s P95 |

## 7. Compliance

| Metric | Target | Window |
|---|---|---|
| DSAR response time | < 30 days (statutory) | per request |
| Breach notification time | < 72 hours (statutory) | per breach |
| Audit event retention | per category policy | continuous |
| Tamper-evidence chain verification | 100% match | hourly |

## 8. SLO Breach Procedure

1. **Detection:** Prometheus alert fires or dashboard panel crosses threshold.
2. **Triage:** Identify affected component and blast radius.
3. **Mitigation:** Execute relevant runbook; restore service within SLO window
   if possible.
4. **Postmortem:** If SLO was breached for > 1 hour or affected > 10% of
   tenants, file a postmortem per `postmortem-template.md`.
5. **Error budget:** Track monthly error budget consumption in Grafana SLO
   dashboard. If error budget is > 90% consumed, freeze non-critical deploys.

## 9. Dashboard

- **Primary:** `monitoring/grafana/dashboards/hub-overview.json`
- **SLO-specific:** `monitoring/grafana/dashboards/api-performance.json`
- **Health:** `GET /api/v1/health/` — real-time dependency status
