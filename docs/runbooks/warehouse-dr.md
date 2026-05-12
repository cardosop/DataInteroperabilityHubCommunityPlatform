# Warehouse Connectivity DR Runbook (Phase 275.E.3j)

## SLO Numbers
- Live-query p95: ≤ 5s (cached), ≤ 30s (fresh)
- Success rate: ≥ 99.5%
- Export cron: ≥ 99% on-time delivery

## RPO / RTO
- Cached rows: best-effort (regenerable from warehouse)
- Audit + creds: matches Hub-DB RPO (15 min)
- RTO: < 1 hour for warehouse credential rotation

## DR Procedure
1. Detect: Grafana warehouse_query_error_rate panel fires
2. Diagnose: check warehouse circuit-breaker state, credential age
3. Recover: rotate credentials via ExternalSecrets, re-enable circuit
