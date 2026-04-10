# UC-TA-007: Monitor Cost Tracking

**Persona:** [Marketplace Platform Admin (MPA)](../personas/marketplace-platform-admin/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_commands_real_api.py::test_cost_tracking`

## Description

A Marketplace Platform Admin reviews the tenant's platform costs,
resource quotas, and billing dashboards to monitor spending trends,
identify cost anomalies, and ensure the tenant operates within its
budgeted limits. The cost-tracking view consolidates compute, storage,
API usage, and marketplace transaction fees into a single pane.

## Preconditions

- The user holds the `MARKETPLACE_ADMIN`, `TENANT_ADMIN`, or
  `PLATFORM_ADMIN` role.
- The tenant's billing integration is active and metering data is
  flowing (see [Billing](../../concepts/billing.md)).
- At least one billing period has elapsed (or the current period has
  accrued usage).

## Steps

1. MPA navigates to "Admin > Cost & Billing" or calls
   `GET /api/v1/billing/costs?tenant_id={id}&period=current` to
   retrieve the current billing summary.
2. The API returns a cost breakdown:
   - **Compute:** Processing jobs (DQ runs, compliance scans,
     transformations) measured in compute-minutes.
   - **Storage:** Object-storage usage in GB-months.
   - **API calls:** Total inbound API requests to tenant endpoints.
   - **Marketplace fees:** Transaction commissions on marketplace
     sales and usage-based revenue share.
   - **Total cost:** Aggregate across all dimensions.
3. MPA drills into a specific cost category by calling
   `GET /api/v1/billing/costs/detail?category=compute&period=current`
   to see per-asset and per-job breakdowns.
4. MPA reviews quota utilization via
   `GET /api/v1/billing/quotas?tenant_id={id}`:
   - Storage quota: used / allocated (e.g., 45 GB / 100 GB).
   - Seat quota: active members / max seats.
   - API rate limit: current usage vs. plan limit.
5. MPA configures cost alerts via
   `POST /api/v1/billing/alerts` with
   `{ threshold_percent: 80, category: "total", channels: ["email"] }`.
   An alert fires when spending reaches 80% of the billing period budget.
6. MPA reviews historical trends via
   `GET /api/v1/billing/costs?period=last_6_months` which returns
   month-by-month cost data for trend analysis.
7. MPA exports the cost report for finance review via
   `GET /api/v1/billing/costs/export?format=csv&period=2026-Q1`.

## Expected Outcome

- The MPA has a comprehensive view of current and historical costs
  across all metered dimensions.
- Quota utilization is visible with clear indicators for approaching
  limits.
- Cost alerts are configured and fire when thresholds are breached.
- Cost data is exportable in CSV for downstream financial reporting.
- An `AUDIT_COST_ALERT_CONFIGURED` event is recorded in the
  [audit log](../../concepts/audit-events.md).

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Billing integration inactive | `422` with `BILLING_NOT_CONFIGURED` code |
| No data for requested period | `200 OK` with zero-value breakdown |
| Invalid period format | `422 Unprocessable Entity` |
| Tenant not found | `404 Not Found` |

## Related

- Concepts: [Billing](../../concepts/billing.md), [Tenants](../../concepts/tenants.md), [Audit Events](../../concepts/audit-events.md)
- Journeys: [JOURNEY-TA-007 -- Monitor Cost Tracking](../journeys/JOURNEY-TA-007.md)
- Personas: [Marketplace Platform Admin](../personas/marketplace-platform-admin/index.md)
