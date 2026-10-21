# JOURNEY-CPO-010: Review Retention Reports

**Persona:** [Compliance & Privacy Officer](../personas/compliance-privacy-officer/)
**Use Cases:** UC-COMP-009, UC-COMP-010

## Overview

A Compliance Officer regularly reviews retention reports to monitor
upcoming data expirations, confirm that auto-purge is executing
correctly, decide whether to extend retention for specific assets,
and export reports for regulatory audits and management review.

## Journey Steps

1. **Access retention dashboard** — The CPO navigates to
   "Compliance > Retention Reports." The dashboard shows a summary
   of all [assets](../concepts/assets.md) grouped by retention
   status:

   - **Active:** Within retention period, no action needed.
   - **Expiring soon:** Within the notification window (30/14/7 days).
   - **Expired:** Retention period elapsed, pending auto-purge or
     manual action.
   - **Purged:** Successfully deleted, metadata retained.
   - **Legal hold:** Exempt from auto-purge.

   KPI cards show total assets under retention, percentage approaching
   expiry, and purge success rate.

2. **Review upcoming expirations** — The CPO filters to "Expiring
   soon" and reviews each asset. For each asset the dashboard shows
   the retention rule applied, original ingestion date, calculated
   expiry date, current compliance status, and the configured expiry
   action (archive or purge). The CPO can sort by expiry date to
   prioritize review.

3. **Extend or confirm deletion** — For each expiring asset the CPO
   takes one of three actions:

   - **Confirm deletion:** The asset will be purged on the expiry
     date as scheduled. No further action needed.
   - **Extend retention:** The CPO sets a new retention end date with
     a justification note (e.g., "Ongoing regulatory inquiry"). The
     extension is logged as an [audit event](../concepts/audit-events.md).
   - **Apply legal hold:** The CPO places the asset under legal hold,
     indefinitely suspending auto-purge until the hold is removed.

4. **Review purge history** — The CPO views the history of completed
   purge operations, including the asset name, purge date, retention
   rule that triggered the purge, data volume deleted, and whether
   the metadata was preserved. Failed purges are highlighted with
   the failure reason (e.g., active marketplace subscriptions
   preventing deletion).

5. **Export report** — The CPO exports the retention report in PDF
   or CSV format. The report includes:

   - Executive summary with KPIs.
   - Full list of assets by retention status.
   - Upcoming expirations with configured actions.
   - Purge history for the selected time period.
   - Exceptions and extensions with justifications.

   The export is timestamped and includes the CPO's identity for
   audit purposes.

6. **Schedule recurring reports** — The CPO configures automated
   report generation and delivery. Reports can be emailed weekly
   or monthly to a distribution list (e.g., legal team, DPO, CISO).
   Each automated report is also stored in the platform's compliance
   document repository.

## Success Criteria

- The retention dashboard accurately reflects current retention status
  for all assets in the tenant.
- The CPO can extend retention or apply legal holds with full
  auditability.
- Purge history is complete with no gaps in the record.
- Exported reports contain all required fields for regulatory review.
- Automated report delivery works on schedule.
- All retention decisions (confirm, extend, hold) produce audit events.

## Related

- Concepts: [Governance](../concepts/governance.md), [Assets](../concepts/assets.md), [Audit Events](../concepts/audit-events.md)
- How-To: [CPO How-To Guides](../personas/compliance-privacy-officer/how-to/)
- Journeys: [JOURNEY-CPO-009](JOURNEY-CPO-009.md) (Configure Retention), [JOURNEY-CPO-007](JOURNEY-CPO-007.md) (GDPR Erasure)
