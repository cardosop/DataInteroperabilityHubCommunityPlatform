# Service Level Objectives — Meshant Platform

**Owner:** platform-eng@meshant.com | **Last Updated:** 2026-05-20

## Core SLOs

| # | Service | SLO | Target | Window | Alert |
|---|---------|-----|--------|--------|-------|
| 1 | API availability | Uptime | ≥ 99.9% | 30 days | `APIAvailabilityLow` |
| 2 | API latency | p95 response | < 500ms | 1 hour | `APILatencyP95High` |
| 3 | DQ run success rate | Success rate | ≥ 99% | 15 min | `DQRunFailureRateHigh` |
| 4 | Compliance scan success | Success rate | ≥ 99% | 15 min | `ComplianceScanFailureHigh` |
| 5 | Job processing latency | p95 completion | < 5 min | 1 hour | `JobProcessingSlow` |
| 6 | Event bus delivery | Delivery rate | ≥ 99.9% | 1 hour | `EventBusDeliveryLow` |
| 7 | Search query latency | p95 response | < 200ms | 1 hour | `SearchQuerySlow` |
| 8 | Database connection pool | Usage | < 80% | 5 min | `DBConnectionPoolHigh` |

## Error Budgets

| Service | Monthly budget | Burn rate alert |
|---------|---------------|-----------------|
| API | 43.2 min/month | > 10% consumed in 1h |
| DQ runs | 7.2 hours/month | > 100 failed runs in 15m |
| Search | 43.2 min/month | > 100 slow queries in 15m |

## Measurement

All SLOs measured via Prometheus metrics and Grafana dashboards.
Error budgets consumed by: planned maintenance, deploys, incidents.

## Review Cadence

- Monthly SLO review: first Monday of each month
- Quarterly SLO adjustment: Jan, Apr, Jul, Oct
- Annual SLO ratification: January
