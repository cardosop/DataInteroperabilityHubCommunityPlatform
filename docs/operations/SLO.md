# Platform Service Level Objectives (SLO)

**Version**: 1.0 | **Last Updated**: 2026-05-20 | **Owner**: Infrastructure Engineering

## SLO Targets

| Service | Metric | Target | Window | Measurement |
|---------|--------|--------|--------|-------------|
| API Gateway | Availability | 99.5% | Monthly | `(total_requests - 5xx_errors) / total_requests` |
| Search | Latency (p95) | < 500ms | Monthly | `histogram_quantile(0.95, search_request_duration_seconds)` |
| SPARQL | Latency (p95) | < 2s | Monthly | `histogram_quantile(0.95, sparql_execution_seconds)` |
| Asset Activation | Latency (p95) | < 30s | Monthly | `histogram_quantile(0.95, asset_activation_duration_seconds)` |
| Frontend | LCP (p75) | < 2.5s | Monthly | `histogram_quantile(0.75, frontend_lcp_seconds)` |
| Frontend | CLS (p75) | < 0.1 | Monthly | `histogram_quantile(0.75, frontend_cls_score)` |

## Error Budget

The error budget is the amount of unreliability allowed per month while still meeting the SLO.

| SLO | Monthly Error Budget | Formula |
|-----|---------------------|---------|
| Availability 99.5% | 0.5% of requests | `total_requests * 0.005` |
| Search p95 < 500ms | 5% of requests | `total_search_requests * 0.05` |
| SPARQL p95 < 2s | 5% of requests | `total_sparql_requests * 0.05` |
| Asset p95 < 30s | 5% of activations | `total_activations * 0.05` |

## Burn-Rate Alerts

Burn rate = (error budget consumed / time window ratio). Alert when budget is burning too fast.

| Alert | Burn Rate | Window | Action | Priority |
|-------|-----------|--------|--------|----------|
| **Critical burn** | > 5% budget consumed in 1h | 1 hour | Page on-call (P1) | Critical |
| **Warning burn** | > 10% budget consumed in 30d | 30 days | Create Jira ticket (P2) | Warning |
| **Budget exhausted** | 100% budget consumed | Monthly | Escalate to VP Engineering | Critical |

### Prometheus Alert Rules

```yaml
# Critical: 5% of monthly error budget burned in 1 hour
- alert: HighErrorBurnRate
  expr: |
    (
      sum(rate(http_requests_total{status=~"5.."}[1h]))
      /
      (sum(rate(http_requests_total[30d])) * 0.005)
    ) > 5
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Error budget burn rate > 5% in 1h"
    runbook: docs/runbooks/RB-SLO-001-error-budget-burn.md

# Warning: 10% of monthly error budget burned in 30 days
- alert: MonthlyErrorBudgetWarning
  expr: |
    (
      sum(increase(http_requests_total{status=~"5.."}[30d]))
      /
      (sum(increase(http_requests_total[30d])) * 0.005)
    ) > 0.10
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "Monthly error budget > 10% consumed"
    runbook: docs/runbooks/RB-SLO-001-error-budget-burn.md

# Latency SLO violations
- alert: SearchLatencySLO
  expr: histogram_quantile(0.95, rate(search_request_duration_seconds_bucket[30d])) > 0.5
  for: 15m
  labels:
    severity: warning
  annotations:
    summary: "Search p95 latency exceeds 500ms SLO"

- alert: SPARQLLatencySLO
  expr: histogram_quantile(0.95, rate(sparql_execution_seconds_bucket[30d])) > 2
  for: 15m
  labels:
    severity: warning
  annotations:
    summary: "SPARQL p95 latency exceeds 2s SLO"
```

## Measurement Methodology

- **Availability**: Measured at the API Gateway (Traefik) level — counts all HTTP requests, excluding health check probes (`/health/*`)
- **Latency**: Measured via OpenTelemetry histograms exported from each service
- **Frontend metrics**: Measured via `web-vitals` library, exported to `frontend_lcp_seconds` and `frontend_cls_score` metrics via the `frontend/src/shared/telemetry/` module
- **SLO compliance window**: Rolling 30-day window, recalculated daily

## Exclusions

The following are excluded from SLO calculation:
- Requests resulting in HTTP 429 (rate-limited) — counted separately as capacity signal
- Requests resulting in HTTP 401/403 (auth failures) — not a service reliability issue
- Requests to `/health/*` endpoints (probes)
- Requests during declared maintenance windows (per `docs/operations/maintenance-template.md`)
