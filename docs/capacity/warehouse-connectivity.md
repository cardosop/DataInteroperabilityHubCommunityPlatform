# Warehouse Connectivity Capacity Sizing (Phase 275.E.3f)

## Query Volume Estimates
- Per-tenant: ~100 live queries/day (initial), scaling to ~1000/day
- Cache hit rate target: 80% (300s TTL)
- Max concurrent queries per tenant: 5 (semaphore-enforced)

## Cache-Row Memory
- Average row: ~200 bytes × 100 rows/query × 1000 cached queries = ~20 MB/tenant
- Redis memory per tenant: ~20 MB
- Cardinality cap: 10,000 keys per tenant

## Connection Pool Sizing
- Min: 2 connections per tenant
- Max: 10 connections per tenant
- Idle timeout: 300s

## P95 Latency Targets
- Cached: ≤ 5s
- Fresh (live query): ≤ 30s
- Success rate: ≥ 99.5%

## Prometheus Cardinality Budget
- warehouse_query_total: ~4 warehouses × ~100 tenants × 3 statuses = 1200 series
- warehouse_query_duration_seconds: same cardinality = 1200 series
- tenant_id label capped at top-100 tenants per metric (overflow bucket)
- query_id ONLY on trace spans, NEVER on Prometheus labels
