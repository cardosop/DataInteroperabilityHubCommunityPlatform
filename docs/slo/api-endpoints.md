# API Endpoint SLOs — Phase 277.B.049

Extends Phase 274.17.3 chain SLO pattern to user-facing API endpoints.
All p95 targets sourced from 277.A.6 performance audit.

## SLO Table

| # | Endpoint | p95 Latency | Error Rate | Window | Rationale |
|---|---|---|---|---|---|
| 1 | `POST /auth/login/` | < 500ms | < 0.5% | 28 days | Login is the gating user experience. Slow login = user churn. |
| 2 | `GET /api/v1/assets/` | < 200ms | < 0.1% | 28 days | Asset list is the DPO's primary workspace. Cache-hit path must be sub-200ms. |
| 3 | `GET /api/v1/marketplace/listings/` | < 500ms | < 0.5% | 28 days | Marketplace search is the consumer's discovery surface. |
| 4 | `POST /api/v1/compliance/runs/` | < 2s | < 1.0% | 28 days | Compliance trigger is async — request-response must be fast even if scan is slow. |
| 5 | `POST /api/v1/audit/events/` | < 50ms | < 0.01% | 28 days | Audit write is on the hot path of every mutation. Must be sub-50ms. |
| 6 | `GET /api/v1/semantic/sparql` | < 5s | < 1.0% | 28 days | SPARQL queries go to external Fuseki sidecar. p95 allows for cold-start. |
| 7 | `GET /api/v1/datasets/{id}/rows/` | < 30s fresh / < 5s cached | < 1.0% | 28 days | Records API can return large datasets. Fresh (warehouse) queries are slow; cached file-backed queries are fast. |
| 8 | Business rules chain execution | < 50ms | < 0.01% | 28 days | Chain runner overhead (Phase 274.17.3). |
| 9 | `GET /api/v1/search/` | < 100ms | < 0.5% | 28 days | Search suggestions are autocomplete UX. |
| 10 | SSE stream connect | < 200ms | < 1.0% | 28 days | Server-Sent Events connection setup time. |

## Measurement

Metrics sourced from:
- `http_request_duration_seconds` histogram (gunicorn/prometheus-client)
- `business_rules_chain_duration_ms` from OTel spans (chain execution)
- `api_response_time_seconds` from middleware timing

## Prometheus Recording Rules

Defined in `monitoring/prometheus/rules/api-slos.yml`. Follow the Phase 274.17.3
pattern: `record` rules compute p95 from histograms (quantile_over_time), `alert`
rules in `monitoring/prometheus/alerts/api-slos.yml` fire on SLO breach.

## Alerting

| Alert | Condition | Severity | Runbook |
|---|---|---|---|
| `ApiEndpointLatencyHigh` | p95 > target for 4 consecutive 5m windows (20m) | warning | Investigate recent deploy, DB pool, or downstream dependency |
| `ApiEndpointErrorRateHigh` | error_rate > target for 4 consecutive 5m windows | critical | Check error logs, circuit-breaker status, downstream health |

## Review Cadence

SLO targets reviewed quarterly. Adjust based on production p95 trends.
