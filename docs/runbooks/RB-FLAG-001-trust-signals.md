# RB-FLAG-001 — Trust Signals Feature Flag

**Flag:** `trust_signals_enabled`
**Stage:** GA
**Owner:** catalog-eng@meshant.com
**Created:** 2026-05-16 (Phase 283.6.4)

## Symptom Index

| Symptom | Likely cause | First checks |
|---------|-------------|--------------|
| Badges not rendering on catalogue cards | Flag disabled for tenant | `GET /api/v1/admin/tenants/{id}/feature-flags/` → `trust_signals_enabled` |
| Freshness indicators stale (>24h) | Trust signal computation job backlog | `trust_signal_computation_duration_seconds`; Redis queue depth |
| Lineage badges missing | `versioning_enabled` also required; lineage index stale | Check both flags; `lineage_edge_sync_drift_total` |
| All badges showing "unknown" | Computation service degraded | `trust_signal_computation_errors_total`; service health endpoint |

## Metrics

- **Dashboard:** `monitoring/grafana/dashboards/catalogue.json`
- **Primary:** `trust_signal_computation_duration_seconds{signal_type}`
- **Error rate:** `trust_signal_computation_errors_total`
- **Audit:** `TRUST_SIGNAL_COMPUTED` events per `resource_type`

## Execution Checklist

1. Verify flag state: `GET /api/v1/admin/tenants/{id}/feature-flags/`
2. Check computation job health: `trust_signal_computation_duration_seconds` < 60s p95
3. Inspect signal types: freshness, completeness, lineage, certification — all four must report
4. Badge rendering: verify catalogue card shows all active signal badges
5. Flag flip audit: `TENANT_FEATURE_FLAG_FLIPPED` with `flag=trust_signals_enabled`

## Escalation

- **P3** — Individual badge type degraded (>50% stale)
- **P2** — All badges showing "unknown" across multiple tenants
- **P1** — Flag flip causes catalogue page crash (rollback flag immediately)

## Maintenance

- **Owner:** Catalog Engineering
- **Last reviewed:** 2026-05-16
- **Next review:** 2026-08-16
