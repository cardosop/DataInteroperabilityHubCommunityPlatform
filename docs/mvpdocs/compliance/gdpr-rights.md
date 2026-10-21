# GDPR Data Subject Rights

Meshant implements the core data subject rights mandated by the General Data
Protection Regulation (Articles 15 through 21). These rights apply to any
[tenant](../concepts/tenants.md) that has GDPR listed in its
`compliance_regulations` configuration.

All rights requests are tracked end-to-end in the [audit trail](audit-trail.md)
and must be fulfilled within the GDPR-mandated 30-day response window. The
platform enforces this deadline by surfacing overdue requests in the governance
dashboard.

---

## Right to Access (Article 15)

Data subjects may request a copy of all personal data held about them. Meshant
supports this through the data export workflow:

1. An authorized user submits an access request via the API or CLI, specifying
   the data subject identifier (e.g. email address).
2. The platform scans all [assets](../concepts/assets.md) within the tenant for
   records matching the identifier using the PII detection classifiers.
3. A portable export package (JSON or CSV) is generated containing every matched
   record along with metadata about processing purposes and retention periods.
4. The export is made available for secure download with a time-limited URL.

---

## Right to Erasure (Article 17)

Also known as the "Right to be Forgotten." When a valid erasure request is
received, Meshant executes the following deletion workflow:

1. All records matching the data subject identifier are located across every
   asset in the tenant.
2. Matched records are permanently deleted from primary storage, search indices,
   and backups.
3. A compliance run verifies that no residual copies remain.
4. An audit event records the erasure, including which assets were affected, but
   does not retain the deleted personal data itself.

This workflow maps to use case **UC-GOV-ADV-002** (GDPR Right to be Forgotten).
See the [Governance concept](../concepts/governance.md) for the broader policy
framework.

---

## Right to Data Portability (Article 20)

Data subjects may request their data in a structured, commonly used,
machine-readable format. The same export mechanism used for the right to access
produces JSON output that satisfies this requirement. Where the data subject
requests transfer to another controller, Meshant supports direct API-to-API
transfer to a designated endpoint.

---

## Right to Rectification (Article 16)

Data subjects may request correction of inaccurate personal data. Rectification
requests trigger a review workflow:

1. The request is logged and assigned to the data steward for the relevant asset.
2. The steward reviews the requested change and either applies it or provides a
   documented justification for refusal.
3. The outcome is recorded in the audit trail.

---

## Consent Management

GDPR requires a lawful basis for processing, and consent is one of the most
common bases. Meshant tracks consent at the individual data subject level:

- **Consent records** store the scope (which processing activities are covered),
  the timestamp of consent, and the method by which consent was obtained.
- **Withdrawal** is supported at any time. When consent is withdrawn, the
  platform triggers a review of all assets that relied on that consent as their
  lawful basis.
- **Compliance runs** verify that no asset is being processed without a valid
  lawful basis.

## Further Reading

- [Regulations](regulations.md)
- [Audit Trail](audit-trail.md)
- [Governance concept](../concepts/governance.md)
- [Compliance Runs concept](../concepts/compliance-runs.md)
