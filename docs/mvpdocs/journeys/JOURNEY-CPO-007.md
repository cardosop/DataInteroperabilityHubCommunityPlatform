# JOURNEY-CPO-007: Execute GDPR Right to be Forgotten

**Persona:** [Compliance & Privacy Officer](../personas/compliance-privacy-officer/)
**Use Cases:** UC-COMP-005, UC-GDPR-001

## Overview

A Compliance Officer processes a GDPR Article 17 erasure request
("right to be forgotten") by identifying all assets containing the
data subject's personal data, executing the erasure across affected
assets, verifying completion, and recording the entire process in
the audit trail for regulatory evidence.

## Journey Steps

1. **Receive erasure request** — The CPO receives a data subject
   erasure request via the platform's GDPR request intake form, email,
   or an external ticketing system. The request includes the data
   subject identifier (e.g., email, customer ID) and the legal basis
   for erasure. The CPO creates a GDPR request record in the platform
   with status `received`.

2. **Identify affected assets** — The CPO uses the platform's
   cross-asset search to find all [assets](../concepts/assets.md)
   containing data matching the subject identifier. The search
   leverages [compliance run](../concepts/compliance-runs.md) results
   and column-level PII annotations to narrow the scope. The platform
   returns a list of affected assets with the specific columns and
   approximate row counts.

3. **Execute erasure** — For each affected asset the CPO initiates
   erasure. The platform supports multiple erasure strategies:

   - **Hard delete:** Rows matching the subject identifier are
     permanently removed from the dataset.
   - **Anonymization:** PII fields are replaced with anonymized
     values (hashed, generalized, or nulled) while preserving
     non-identifying data for analytics.
   - **Encryption key destruction:** If the data is encrypted with
     a per-subject key, the key is destroyed rendering the data
     unrecoverable.

   The CPO selects the appropriate strategy per asset based on legal
   requirements and data utility considerations.

4. **Verify completion** — After erasure the platform runs a
   verification scan that searches for any remaining instances of the
   subject identifier across all affected assets. The CPO reviews the
   verification report. If residual data is found the erasure is
   re-executed on the missed records.

5. **Log to audit trail** — The platform records a comprehensive
   [audit event](../concepts/audit-events.md) chain for the entire
   GDPR request: receipt, asset identification, erasure execution per
   asset (including strategy used), verification result, and closure.
   The audit records are retained for the legally mandated period
   (typically 3 years) and are exportable for regulatory inspection.

6. **Close request** — The CPO marks the GDPR request as `completed`
   and generates a completion certificate. The data subject is
   notified (if notification was requested) that their erasure request
   has been fulfilled.

## Success Criteria

- All assets containing the data subject's PII are identified.
- Erasure is executed with the appropriate strategy per asset.
- The verification scan confirms zero residual data for the subject.
- The full request lifecycle is recorded in the audit trail.
- The request is completed within the GDPR-mandated 30-day window.
- A completion certificate is generated and available for export.

## Related

- Concepts: [Compliance Runs](../concepts/compliance-runs.md), [Audit Events](../concepts/audit-events.md), [Governance](../concepts/governance.md), [Assets](../concepts/assets.md)
- How-To: [CPO How-To Guides](../personas/compliance-privacy-officer/how-to/)
- Journeys: [JOURNEY-CPO-008](JOURNEY-CPO-008.md) (Manage Consent), [JOURNEY-CPO-001](JOURNEY-CPO-001.md) (Run Compliance Scan)
