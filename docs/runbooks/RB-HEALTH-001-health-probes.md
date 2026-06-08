# RB-HEALTH-001 — Health Probes & SLO Monitoring

**Date:** 2026-05-20
**SLO document:** `docs/slo/service-level-objectives.md`
**Health endpoint:** `GET /api/v1/health/`

## 1. Overview

Operational procedure for the Meshant health probe subsystem — liveness,
readiness, dependency health, business-rules degradation, and SLO
monitoring. Covers the unified health endpoint (Phase 274.16.9) and
the SLO dashboard.

## 2. When This Runbook Fires

- **Prometheus alert `ServiceDown`** — any core service health check fails.
- **Prometheus alert `DatabaseConnectionPoolExhausted`** — DB connection pool > 80.
- **Prometheus alert `JobSLOViolation`** — job execution P95 exceeds 2x baseline.
- **Health endpoint returns degraded** — any dependency reports unhealthy.
- **Scheduled SLO review** — monthly SLO compliance report.

## 3. Scope

1. **Liveness probe** — `GET /api/v1/health/live/` returns 200 if the
   process is alive.
2. **Readiness probe** — `GET /api/v1/health/ready/` returns 200 if the
   service can accept traffic (DB reachable, migrations applied, Redis
   connected).
3. **Dependency health** — `GET /api/v1/health/` returns status for each
   dependency: PostgreSQL, Redis (cache/queue/events/channels), Fuseki,
   Stripe API, compliance-service, semantic-service, Prefect API.
4. **Business-rules health** — `GET /api/v1/health/business-rules` returns
   `{status, degraded_rules, degraded_count}`. SRE alert fires when
   `degraded_count > 0`.
5. **SLO monitoring** — published SLOs for API latency, error rate,
   job processing time, and data freshness. Tracked in Grafana SLO
   dashboard.

## 4. Published SLOs

| SLO | Target | Measurement Window |
|---|---|---|
| API availability | 99.9% | 30 days |
| API P95 latency | < 500ms | 5 minutes |
| API error rate | < 0.1% | 30 days |
| Job processing P95 | < 2x 24h baseline | 30 minutes |
| Compliance scan latency | < 30s P95 | 5 minutes |
| Data freshness (scheduled ingestion) | < 2x configured interval | per ingestion |

## 5. Investigation Procedure

### 5.1 — Check health endpoint

```bash
curl -sf https://api.stagingmeshant-internal.example.com/api/v1/health/ | jq .
```

Expected response:
```json
{
  "status": "healthy",
  "dependencies": {
    "database": "healthy",
    "redis_cache": "healthy",
    "redis_queue": "healthy",
    "fuseki": "healthy",
    "stripe": "healthy",
    "compliance_service": "healthy"
  },
  "timestamp": "2026-05-20T12:00:00Z"
}
```

### 5.2 — Check business-rules health

```bash
curl -sf https://api.stagingmeshant-internal.example.com/api/v1/health/business-rules | jq .
```

### 5.3 — Check dependency-specific health

```bash
# PostgreSQL
kubectl exec -n hub-staging deployment/api-service -- python manage.py dbshell -c "SELECT 1"

# Redis
redis-cli -h redis-queue.hub-staging PING

# Fuseki
curl -sf http://fuseki.hub-staging:3030/$/ping
```

## 6. Remediation

### Service down

1. Check pod status: `kubectl get pods -n hub-staging`
2. Check recent events: `kubectl describe pod <pod-name> -n hub-staging`
3. Check logs: `kubectl logs -n hub-staging <pod-name> --tail=100`
4. If OOMKilled: increase memory limits in Helm values
5. If CrashLoopBackOff: check startup probe logs

### Database unhealthy

1. Check connection pool: `kubectl exec -n hub-staging deployment/pgbouncer -- ...`
2. Check replication lag: see `pg_replication_lag_seconds` in Prometheus
3. If pool exhausted: scale API replicas or increase `default_pool_size`

### Redis unhealthy

1. Check Redis pod: `kubectl get pods -n hub-staging -l app=redis`
2. Check memory: `redis-cli -h <host> INFO memory`
3. If OOM: increase maxmemory or evict keys

### Business-rules degraded

1. `GET /api/v1/health/business-rules` returns the list of degraded rules
2. Check the specific rule's implementation for exceptions
3. If transient: rules auto-recover on next evaluation
4. If persistent: disable the rule until fix is deployed

## 7. Forensic Queries

```bash
# Historical health check results (last 24h)
kubectl logs -n hub-staging deployment/api-service --since=24h | grep "health_check"

# Dependency failure rate
curl -sf https://prometheus.stagingmeshant-internal.example.com/api/v1/query \
  --data 'query=rate(health_check_failures_total[1h])' | jq .
```

## 8. Related

- **Health probes**: `hub/apps/observability/health_views.py`
- **SLO document**: `docs/slo/service-level-objectives.md`
- **Alerts**: `monitoring/prometheus/alerts.yml` — `ServiceDown`, `HighErrorRate`, `HighLatency`
- **Dashboards**:
  - `monitoring/grafana/dashboards/hub-overview.json`
  - `monitoring/grafana/dashboards/api-performance.json`
  - `monitoring/grafana/dashboards/database-performance.json`
  - `monitoring/grafana/dashboards/engineering-health.json`
- **Cross-runbook**:
  - [`postgres-runbook.md`](postgres-runbook.md)
  - [`marquez-outage.md`](marquez-outage.md)
  - [`vendor-failure-stripe.md`](vendor-failure-stripe.md)

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-20
- **Next review**: 2026-08-18
