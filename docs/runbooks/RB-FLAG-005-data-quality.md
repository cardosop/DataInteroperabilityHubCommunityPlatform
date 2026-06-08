# RB-FLAG-005 — Data Quality Feature Flags

**Flags:** `data_quality_enabled`, `data_quality_advanced_enabled`
**Stage:** GA (both)
**Owner:** dq-eng@meshant.com
**Created:** 2026-05-16 (Phase 283.6.4)

## Scope

- `data_quality_enabled` — Master kill-switch for the DQ feature. Default ON for all tenants.
- `data_quality_advanced_enabled` — Gates advanced endpoints (trends, scorecards, anomalies, RCA). Default ON for new tenants; off for existing.

## Symptom Index

| Symptom | Likely cause | First checks |
|---------|-------------|--------------|
| DQ run creation returns 403 | `data_quality_enabled=False` | Flag state; tenant capabilities |
| Trends/scorecards return 403 | `data_quality_advanced_enabled=False` | Flag state; advanced flag requires base flag |
| DQ run stuck in PENDING | DQ worker queue backlog; engine selection failure | `dq_run_duration_seconds`; worker health; engine (`_gx` / `_soda`) |
| Rule evaluation timeout | Complex expectation; data volume spike | `dq_rule_evaluation_duration_seconds`; query plan; row count |
| Anomaly detection returns empty | Insufficient history for baseline | `dq_anomaly_baseline_samples`; minimum 14 days of data required |
| RCA returns 403 but scorecards work | `data_quality_advanced_enabled=False` (RCA is advanced-only) | Flag state; RCA requires advanced flag |

## Metrics

- **Dashboard:** `monitoring/grafana/dashboards/data-quality.json`
- **Primary:** `dq_run_duration_seconds{engine, status}`
- **Rule evaluation:** `dq_rule_evaluation_total{rule_name, result}`
- **Advanced:** `dq_advanced_query_duration_seconds{endpoint}`
- **Audit:** `DQ_RUN_COMPLETED`, `DQ_RULE_FAILED`, `ADVANCED_DQ_ACCESSED`

## Execution Checklist

1. Verify flag state: `GET /api/v1/admin/tenants/{id}/feature-flags/`
2. Check engine health: GX adapter + Soda adapter both reachable
3. Inspect recent runs: `GET /api/v1/dq/runs/?limit=20`
4. Verify rule evaluation: spot-check a passed and failed rule for correctness
5. Advanced features: trends return data, scorecards render, anomalies have baselines, RCA paths resolve
6. Flag flip audit: `TENANT_FEATURE_FLAG_FLIPPED` with `flag=data_quality_enabled` or `data_quality_advanced_enabled`

## Escalation

- **P3** — Individual rule evaluation false positive (tune expectation)
- **P2** — DQ worker queue backlog >50 runs or >30min delay
- **P1** — DQ service down; all runs failing across multiple tenants

## Related

- `docs/runbooks/data-quality.md` — DQ operational procedures
- `docs/mvpdocs/concepts/data-quality.md` — DQ concept docs
- `hub/apps/dq/views.py` — DQ REST surface

## Maintenance

- **Owner:** DQ Engineering
- **Last reviewed:** 2026-05-16
- **Next review:** 2026-08-16
