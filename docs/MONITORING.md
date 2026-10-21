# Monitoring

## W3C Trace Context

All services propagate W3C trace context via the `traceparent` and `tracestate` HTTP headers.
Every incoming request to api-service (API Gateway) is assigned a `trace_id` that flows through to downstream services.

## Services with trace context

- **api-service** — generates root spans for HTTP requests; propagates W3C headers to backend services.
- **API Gateway** — injects `traceparent` on every request before it reaches the api-service; records span timings for latency SLO tracking.

## Metrics
Key metrics are exported to Prometheus via `/metrics` endpoints on each service. Dashboards in Grafana track request latency, error rates, and DB connection pools.

## Alerts
Alerting rules are defined in `helm/` and `infrastructure/terraform/` for RDS, Redis, and service-level indicators.
