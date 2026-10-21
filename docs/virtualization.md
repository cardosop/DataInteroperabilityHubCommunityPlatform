# Data Virtualization — Schema Drift Risk

**Status:** CANARY (285.5.3.C, 2026-05-17)
**Feature Flag:** `virtualization_enabled`

## Schema Drift Risk

Virtual datasets are defined as SQL queries over live warehouse sources. Schema
drift occurs when the source table's schema changes (column added, dropped, or
renamed) after a virtual dataset has been created. This can cause:

1. **Query failures** — Virtual queries referencing columns that no longer exist
2. **Silent data corruption** — Implicit type coercion when column types change
3. **Downstream contract violations** — ODCS contracts referencing stale schemas

## Mitigation

- **Schema snapshot on creation:** The source schema is captured in
  `VirtualDataset.source_schema` at creation time for diff comparison.
- **Pre-execution schema check:** `VirtualDatasetViewSet.execute_query()` compares
  the current source schema against the captured snapshot before execution.
- **Drift notification:** Schema mismatch emits a `VIRTUAL_SCHEMA_DRIFT_DETECTED`
  audit event with the diff detail.
- **Manual remediation:** The tenant admin must review and update the virtual
  dataset definition when drift is detected. Automatic schema migration is NOT
  performed — the semantics of the query may need human review.

## Monitoring

- **Dashboard:** `monitoring/grafana/dashboards/virtualization.json`
- **Primary metric:** `virtual_schema_drift_total{tenant_id, dataset_id}`
- **Alert:** Warning at >5 drift events/hour, Critical at >50/hour

## Support Burden

Virtual datasets create an ongoing support obligation because schema drift is
inherent to live warehouse sources. The current CANARY designation limits exposure
to tenants who have opted in and been informed of the drift risk.

## Related

- `hub/apps/virtualization/models.py` — VirtualDataset model
- `hub/apps/virtualization/views.py` — VirtualDatasetViewSet
- `hub/apps/tenants/feature_flag_registry.py` — `virtualization_enabled` flag (CANARY)
- `docs/runbooks/virtualization-drift.md` — (future) schema drift incident response

## Maintenance

- **Owner:** Data Plane Engineering
- **Last reviewed:** 2026-05-17
- **Next review:** 2027-03-01 (per registry comment)
