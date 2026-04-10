# JOURNEY-TA-007: Monitor Cost Tracking

**Persona:** [Marketplace & Platform Admin](../personas/marketplace-platform-admin/)
**Use Cases:** UC-TA-001, UC-BILLING-001

## Overview

A Tenant or Platform Admin monitors platform costs by reviewing the
billing dashboard, analyzing per-tenant cost breakdowns, checking
quota usage against plan limits, configuring budget alerts, and
exporting invoices for accounting. This journey ensures financial
visibility and prevents unexpected cost overruns.

## Journey Steps

1. **Access billing dashboard** — The admin navigates to "Admin >
   Billing" from the main navigation. The dashboard displays a
   month-to-date cost summary, a trend chart showing daily spend over
   the last 90 days, and a cost breakdown by category (storage,
   compute, API calls, marketplace transactions, compliance scans).

2. **Review per-tenant costs** — For platform-level admins managing
   multiple [tenants](../concepts/tenants.md), the dashboard shows a
   tenant-by-tenant cost table. Each row displays the tenant name,
   current plan tier, month-to-date spend, projected month-end spend,
   and variance from the previous month. The admin can click into any
   tenant for a detailed cost breakdown.

3. **Check quota usage** — The admin reviews quota utilization for
   each tenant:

   - **Storage:** GB used vs. plan limit (e.g., 45 GB / 100 GB).
   - **API calls:** Requests this month vs. rate limit
     (e.g., 125K / 500K).
   - **Assets:** Number of active assets vs. plan maximum.
   - **DQ runs:** Scan count vs. included scans per billing period.
   - **Users:** Active users vs. licensed seats.

   Quotas approaching 80% utilization are highlighted in amber;
   those above 90% are in red.

4. **Set budget alerts** — The admin configures budget alerts at
   configurable thresholds (e.g., 50%, 75%, 90%, 100% of monthly
   budget). Alerts are delivered via email and
   [webhooks](../concepts/webhooks.md) to the designated finance
   contact. Each alert includes current spend, projected end-of-month
   total, and the largest cost drivers.

5. **Review line items** — The admin drills into individual cost line
   items for the current or past billing periods. Each item shows the
   resource type, unit count, unit price, and total cost. For
   marketplace transactions the listing name, buyer, and seller are
   included. The admin can filter by date range, cost category, or
   tenant.

6. **Export invoices** — The admin exports invoices in PDF or CSV
   format for any billing period. The PDF invoice includes tenant
   details, itemized charges, applicable taxes, and payment
   information. CSV exports are formatted for import into accounting
   systems (QuickBooks, Xero, SAP).

## Success Criteria

- The billing dashboard loads with accurate, up-to-date cost data
  (refreshed at least hourly).
- Per-tenant cost breakdowns match individual tenant invoices.
- Quota utilization is displayed in real time.
- Budget alerts fire within 15 minutes of threshold breach.
- Exported invoices contain all fields required for accounting.
- All billing configuration changes produce
  [audit events](../concepts/audit-events.md).

## Related

- Concepts: [Billing](../concepts/billing.md), [Tenants](../concepts/tenants.md), [Webhooks](../concepts/webhooks.md), [Audit Events](../concepts/audit-events.md)
- How-To: [MPA How-To Guides](../personas/marketplace-platform-admin/how-to/)
- Journeys: [JOURNEY-TA-008](JOURNEY-TA-008.md) (Configure Integrations), [JOURNEY-PA-001](JOURNEY-PA-001.md) (Onboard Instance)
