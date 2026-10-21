# JOURNEY-DB-015: Set a Databricks Budget

**Persona:** [Marketplace Platform Admin](../personas/marketplace-platform-admin/), Data Product Owner (DPO)
**Use Cases:** UC-DB-015

## Overview

A platform admin sets a Databricks cost budget per tenant — `budget_units_per_hour` (NULL = unlimited, an optional per-warehouse scope) with BLOCK or ALERT overage behavior on the budget row itself. Usage flows into the append-only cost ledger from the hourly `system.billing.usage` sync (`billing_sync` attribution) and, once the exactly-once record fix lands, from per-query attribution by source; a per-tenant Redis rolling-hour window enforces the budget before any warehouse work, and the UI shows the budget rows with the rolling progress.

## Journey Steps

1. **Open the budget page** — The user sees the tenant's budget rows and the rolling usage (the 7.6 budget page surface).
2. **Set a budget** — The user sets the DBU limit per rolling hour and the overage action (BLOCK or ALERT). The mode rides the budget row — no tenant flags.
3. **Watch usage** — The hourly cost-sync job reads `system.billing.usage` on the workspace's RUNNING SQL warehouse under the D12 background identity and appends the delta to the ledger; every row also lands in the rolling-hour window.
4. **Trip the budget** — BLOCK returns HTTP 429 `WAREHOUSE_COST_BUDGET_EXCEEDED` with the audit row on new executions (zero warehouse queries attempted); ALERT emits the near-exceeded audit row and lets the query run. A window-cache outage degrades to the ledger fallback on the alert path — never a false BLOCK.
5. **Recover** — The rolling window drops below the limit and execution resumes automatically.

## Success Criteria

- BLOCK and ALERT paths both emit their audit rows (best-effort — an audit-DB outage never blocks the dispatch).
- Ledger rows attribute cost by source (warehouse query / job run / DLT / `billing_sync`) with exactly ONE record per executed query.
- The sync job runs as an RQ job under `tenant_context` with a helm CronJob entry.

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md), [Feature Availability](../concepts/feature-availability.md), [Audit Events](../concepts/audit-events.md)
- How-To: [Data Engineer How-To Guides](../personas/data-engineer/how-to/)
- Journeys: [JOURNEY-DB-010](JOURNEY-DB-010.md) (Manage SQL Warehouses)
