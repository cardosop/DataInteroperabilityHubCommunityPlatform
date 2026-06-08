# JOURNEY-DS-003 — Monitor Inference

**Persona:** Data Scientist (DS)
**Priority:** P2
**Phase:** 285 (GA)

## Goal

Monitor deployed model inference performance — latency, error rate,
throughput — and set up alerts for degradation.

## Steps

1. **View inference dashboard** (`GET /api/v1/ml/models/{id}/metrics/`):
   See latency percentiles (p50/p95/p99), request count, error rate.

2. **Configure alerts** (`POST /api/v1/ml/models/{id}/alerts/`):
   Set thresholds for latency (>500ms P95), error rate (>5%), or
   throughput drop (>50% vs 24h baseline).

3. **Review inference logs** (`GET /api/v1/ml/models/{id}/inference/?since=1h`):
   Inspect individual inference requests — input shape, output shape,
   response time, error messages.

4. **Roll back if needed** (`POST /api/v1/ml/models/{id}/versions/{vid}/rollback/`):
   If a newly deployed version performs worse, roll back to the
   previous version.

## Expected Outcome

Model inference is monitored with alerts. Degradation is detected and
resolved within SLO window.

## Related

- Feature flag: `ml_enabled` (GA, opt-in)
- Runbook: `docs/runbooks/RB-ML-002-model-deployment-failure.md`
- Dashboard: `monitoring/grafana/dashboards/` (ML inference metrics)
