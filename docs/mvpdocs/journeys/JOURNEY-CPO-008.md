# JOURNEY-CPO-008: Manage Consent Tracking

**Persona:** [Compliance & Privacy Officer](../personas/compliance-privacy-officer/)
**Use Cases:** UC-COMP-006, UC-GDPR-002

## Overview

A Compliance Officer configures and manages consent tracking within
Meshant to ensure that data processing activities are backed by valid,
documented consent from data subjects. This journey covers defining
consent categories, recording consents, monitoring expiry, and handling
withdrawals in compliance with GDPR Article 7 requirements.

## Journey Steps

1. **Configure consent categories** — The CPO navigates to
   "Compliance > Consent Management" and defines the consent
   categories relevant to the tenant's data processing activities.
   Examples include:

   - **Marketing communications:** Consent to receive promotional
     emails.
   - **Analytics processing:** Consent to use personal data for
     analytics.
   - **Third-party sharing:** Consent to share data with marketplace
     consumers.
   - **Profiling:** Consent to automated decision-making.

   Each category includes a purpose description, legal basis
   reference, and default expiry period (e.g., 12 months).

2. **Record consents** — Consents are recorded via the platform API
   when a data subject provides them (e.g., during registration,
   checkout, or a consent management UI). Each consent record includes
   the subject identifier, category, timestamp, collection method
   (web form, API, import), and the specific version of the privacy
   notice the subject agreed to.

3. **Monitor expiry** — The CPO views the consent dashboard showing
   active consents by category, upcoming expirations (30/60/90 day
   windows), and expired consents requiring renewal. The platform sends
   automated email notifications to data subjects 30 days before
   consent expiry, requesting renewal.

4. **Handle withdrawals** — When a data subject withdraws consent the
   platform records the withdrawal with a timestamp and triggers
   downstream actions: data processing for the withdrawn category is
   suspended, affected [assets](../concepts/assets.md) are flagged,
   and the asset owner is notified. Withdrawal does not affect the
   lawfulness of processing performed before the withdrawal.

5. **Audit consent history** — The CPO can view the full consent
   history for any data subject, showing every grant, renewal, and
   withdrawal with timestamps and collection methods. This history
   is available as an [audit event](../concepts/audit-events.md)
   export for regulatory inspection.

6. **Generate consent reports** — The CPO exports consent analytics:
   total active consents by category, opt-in/opt-out rates, average
   consent duration, and renewal rates. Reports can be exported in
   PDF or CSV format for management review or regulatory submission.

## Success Criteria

- Consent categories are configured with correct legal basis references.
- Consent records include all GDPR-required fields (subject, purpose,
  timestamp, method, notice version).
- Expiry notifications are sent 30 days before consent expires.
- Withdrawals are processed immediately and downstream actions fire.
- The full consent history is auditable per data subject.
- Reports accurately reflect current consent status across the tenant.

## Related

- Concepts: [Governance](../concepts/governance.md), [Audit Events](../concepts/audit-events.md), [Users and Roles](../concepts/users-and-roles.md)
- How-To: [CPO How-To Guides](../personas/compliance-privacy-officer/how-to/)
- Journeys: [JOURNEY-CPO-007](JOURNEY-CPO-007.md) (GDPR Erasure), [JOURNEY-CPO-009](JOURNEY-CPO-009.md) (Configure Retention)
