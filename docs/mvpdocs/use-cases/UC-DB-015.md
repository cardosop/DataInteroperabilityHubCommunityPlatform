# UC-DB-015: Set Databricks Budget

**Persona:** [Marketplace Platform Admin](../personas/marketplace-platform-admin/index.md)
**MVP Tier:** :white_check_mark:
**Phase P7 Test:** `hub/apps/databricks_admin/tests/test_budget_journeys.py::TestJOURNEYDB015SetDatabricksBudget::test_block_vs_alert`

## Description

Set per-tenant Databricks cost budgets with BLOCK or ALERT overage behavior, enforced through a per-tenant Redis rolling-hour window fed by the append-only cost ledger (`billing_sync` attribution from the hourly `system.billing.usage` sync; per-query attribution by source lands with the exactly-once record fix).

## Preconditions

- A registered workspace with a RUNNING SQL warehouse mirror and the D12 M2M credential linkage (the cost-sync's fail-closed requirements).
- The cost-sync job (`DATABRICKS_COST_SYNC`) runs hourly under `tenant_context`.

## Steps

1. Admin sets the budget row — `budget_units_per_hour` (NULL = unlimited) + `enforcement_mode` (BLOCK or ALERT; the mode rides the budget row — no tenant flags).
2. The sync job reads `system.billing.usage` and appends the delta to the ledger; every ledger row also lands in the rolling-hour window.
3. New executions check the Redis rolling window before any warehouse work.
4. BLOCK returns 429 `WAREHOUSE_COST_BUDGET_EXCEEDED` with the audit row and zero warehouse queries; ALERT emits the near-exceeded audit row and lets the query run. A cache outage never falsely blocks — the enforcement degrades to the ledger fallback on the alert path.

## Expected Outcome

- The rolling window recovers execution automatically once the consumed hour drains below the budget.
- Ledger rows attribute cost by source (warehouse query / job run / DLT / `billing_sync`) with exactly ONE record per executed query.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Budget exceeded (BLOCK) | `429` with `WAREHOUSE_COST_BUDGET_EXCEEDED` + audit row, no warehouse query |
| Budget exceeded (ALERT) | Near-exceeded audit row fires, execution continues |
| Window cache unavailable | Ledger fallback on the alert path — never a false BLOCK |

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md), [Audit Events](../concepts/audit-events.md)
- Journeys: [JOURNEY-DB-015 -- Set a Databricks Budget](../journeys/JOURNEY-DB-015.md)
- Personas: [Marketplace Platform Admin](../personas/marketplace-platform-admin/index.md)
