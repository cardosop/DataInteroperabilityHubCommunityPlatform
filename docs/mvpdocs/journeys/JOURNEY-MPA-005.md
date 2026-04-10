# JOURNEY-MPA-005: Marketplace Admin Operations

**Persona:** [Marketplace & Platform Admin](../personas/marketplace-platform-admin/)
**Use Cases:** UC-MPA-001, UC-MPA-002, UC-MPA-003

## Overview

A Marketplace Admin performs day-to-day platform operations: reviewing
pending listings for approval, handling disputes between providers and
consumers, monitoring platform-wide metrics, and configuring rate
limits to protect platform stability. This journey ensures the
marketplace maintains quality, trust, and performance.

## Journey Steps

1. **Review pending listings** — The admin navigates to "Admin >
   Listings > Pending Review." A queue shows all
   [marketplace listings](../concepts/marketplace-listings.md)
   submitted by Data Product Owners awaiting approval. Each entry
   displays the asset name, submitting user, submission date, quality
   score, compliance status, and pricing model. The queue is sortable
   by date, risk level, or submitter.

2. **Approve or reject** — The admin opens a pending listing and
   reviews the asset detail: description quality, schema
   documentation, DQ score, compliance badge, and pricing
   appropriateness. The admin can:

   - **Approve:** The listing moves to `live` and becomes
     discoverable in the marketplace. The DPO is notified.
   - **Request revision:** The listing returns to `revision_requested`
     with specific feedback (e.g., "Description too brief," "Pricing
     exceeds category average"). The DPO is notified with action items.
   - **Reject:** The listing is declined with a reason. The DPO can
     re-submit after addressing the issues.

   All decisions are recorded as [audit events](../concepts/audit-events.md).

3. **Handle disputes** — The admin manages disputes raised by
   consumers (e.g., "Data does not match description," "Quality
   degraded since purchase"). The dispute workflow includes:

   - Reviewing the consumer complaint and the listing details.
   - Contacting the DPO for a response.
   - Mediating a resolution (refund, data correction, listing update).
   - Closing the dispute with a documented outcome.

   Escalated disputes that cannot be resolved are flagged for the
   Platform Admin.

4. **Monitor platform metrics** — The admin views the platform-wide
   dashboard showing real-time and historical metrics:

   - **Marketplace health:** Total listings, new listings this week,
     approval rate, average time-to-approval.
   - **Transaction volume:** Purchases per day, revenue trend,
     average transaction value.
   - **User activity:** Active users, new registrations, search
     volume.
   - **Quality overview:** Average quality score across all listed
     assets, compliance pass rate.
   - **System performance:** API latency (p50, p95, p99), error rate,
     uptime.

5. **Configure rate limits** — The admin navigates to "Admin > Rate
   Limits" and configures API rate limits per user role, endpoint
   group, and tenant tier:

   | Role | Endpoint Group | Rate Limit |
   |---|---|---|
   | Consumer | Search / Browse | 100 req/min |
   | DPO | Asset Management | 60 req/min |
   | DE | SDK / API | 200 req/min |
   | Admin | All | 500 req/min |

   Rate limits protect platform stability and ensure fair usage.
   Exceeded limits return `429 Too Many Requests` with a `Retry-After`
   header.

6. **Generate operations report** — The admin exports a periodic
   operations report summarizing listing review activity, dispute
   resolutions, platform metrics, and rate limit violations. Reports
   are available in PDF or CSV format and can be scheduled for
   automatic delivery.

## Success Criteria

- Pending listings are reviewed within the SLA (e.g., 48 hours).
- Approval/rejection decisions include documented rationale.
- Disputes are resolved and closed with both parties notified.
- Platform metrics are accurate and refresh in near real-time.
- Rate limits are enforced consistently with correct HTTP responses.
- All admin operations produce audit events.

## Related

- Concepts: [Marketplace Listings](../concepts/marketplace-listings.md), [Billing](../concepts/billing.md), [Audit Events](../concepts/audit-events.md), [Tenants](../concepts/tenants.md)
- How-To: [MPA How-To Guides](../personas/marketplace-platform-admin/how-to/)
- Journeys: [JOURNEY-PA-001](JOURNEY-PA-001.md) (Onboard Instance), [JOURNEY-TA-007](JOURNEY-TA-007.md) (Monitor Costs), [JOURNEY-DPO-002](JOURNEY-DPO-002.md) (Publish Asset)
