# JOURNEY-CPO-009: Configure Automated Retention

**Persona:** [Compliance & Privacy Officer](../personas/compliance-privacy-officer/)
**Use Cases:** UC-COMP-007, UC-COMP-008

## Overview

A Compliance Officer configures data retention policies so that assets
are automatically purged or archived when their retention period
expires. This journey covers defining retention periods per data
classification, enabling auto-purge, and configuring notifications
to asset owners before deletion occurs.

## Journey Steps

1. **Define retention periods per data class** — The CPO navigates to
   "Compliance > Retention Policies" and creates retention rules based
   on data classification. Each rule maps a classification tag to a
   retention period:

   | Classification | Retention Period | Action on Expiry |
   |---|---|---|
   | `financial-records` | 7 years | Archive then purge |
   | `customer-pii` | 3 years | Purge |
   | `analytics-derived` | 1 year | Archive |
   | `temporary-staging` | 90 days | Purge |

   Rules are applied to [assets](../concepts/assets.md) based on
   their domain tags and compliance scan classifications. Multiple
   rules can apply to a single asset; the longest retention period
   wins.

2. **Enable auto-purge** — The CPO toggles auto-purge for each
   retention rule. When enabled the platform automatically executes
   the configured expiry action (archive or purge) when the retention
   period elapses. Purge permanently deletes the asset data while
   retaining metadata and [audit events](../concepts/audit-events.md)
   for regulatory traceability.

3. **Configure pre-deletion notifications** — The CPO sets up
   notification rules that alert asset owners before auto-purge
   executes. Configurable notification windows (e.g., 30, 14, and
   7 days before expiry) send emails and in-app notifications to the
   asset owner and designated reviewers with a link to extend the
   retention period if justified.

4. **Set exception workflows** — The CPO defines exception criteria
   for assets under legal hold or active regulatory investigation.
   Assets with an active legal hold tag bypass auto-purge regardless
   of their retention period. The CPO can apply and remove legal holds
   from the asset detail page.

5. **Review and activate** — Before activating a new retention policy
   the CPO sees a dry-run impact report showing how many assets would
   be affected, their current state, and estimated deletion dates.
   After review the CPO activates the policy. An `retention.policy_
   activated` audit event is recorded.

6. **Monitor retention execution** — The CPO monitors the retention
   dashboard showing upcoming expirations, recently purged assets,
   and assets on legal hold. Failed purge operations (e.g., due to
   active subscriptions) are flagged for manual resolution.

## Success Criteria

- Retention rules are defined for all relevant data classifications.
- Auto-purge executes on schedule without manual intervention.
- Pre-deletion notifications reach asset owners at all configured
  windows.
- Legal holds correctly prevent auto-purge.
- Purged assets retain metadata and audit trail for traceability.
- The dry-run impact report accurately predicts affected assets.

## Related

- Concepts: [Governance](../concepts/governance.md), [Assets](../concepts/assets.md), [Audit Events](../concepts/audit-events.md)
- How-To: [CPO How-To Guides](../personas/compliance-privacy-officer/how-to/)
- Journeys: [JOURNEY-CPO-010](JOURNEY-CPO-010.md) (Review Retention Reports), [JOURNEY-CPO-007](JOURNEY-CPO-007.md) (GDPR Erasure)
