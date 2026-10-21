# Compliance Posture

Meshant enforces a **fail-closed compliance model**: every data asset must pass
its applicable compliance checks before it can be published, shared, or
exported. Compliance gates cannot be bypassed or overridden by any user role,
including tenant administrators. This design ensures that regulatory violations
are caught at the platform level rather than relying on human discipline.

## Supported Regulations

Meshant ships with built-in rule sets for the following regulatory frameworks:

| Regulation | Jurisdiction | Status |
|---|---|---|
| [GDPR](regulations.md#gdpr) | European Union | MVP |
| [HIPAA](regulations.md#hipaa) | United States (healthcare) | MVP |
| [SOX](regulations.md#sox) | United States (financial reporting) | MVP |
| [LGPD](regulations.md#lgpd) | Brazil | MVP |
| [CCPA](regulations.md#ccpa) | California, United States | MVP |

Each regulation maps to a set of [compliance runs](../concepts/compliance-runs.md)
that are executed automatically when assets transition through their lifecycle.

## Key Capabilities

- **Automated compliance scans** -- assets are scanned against all applicable
  regulation rule sets before they can leave `draft` status.
- **PII detection** -- built-in classifiers identify personally identifiable
  information and flag it for masking, encryption, or removal.
- **Immutable audit trail** -- every mutation, access event, and compliance
  decision is recorded in a tamper-evident log retained for a minimum of three
  years. See [Audit Trail](audit-trail.md).
- **Data residency controls** -- tenant-level configuration restricts where data
  is stored and processed. See [Data Residency](data-residency.md).
- **Consent tracking** -- records and enforces data-subject consent per
  regulation. See [GDPR Rights](gdpr-rights.md).

## Security

Compliance is only meaningful when the underlying platform is secure. Meshant
applies defense-in-depth controls including encryption at rest and in transit,
JWT-based authentication, RBAC, rate limiting, and continuous dependency
scanning. See [Security Posture](security-posture.md) for details.

## Vulnerability Reporting

If you discover a security issue, please follow the
[Responsible Disclosure Policy](vulnerability-disclosure.md).

## Sub-pages

| Page | Description |
|---|---|
| [Regulations](regulations.md) | Detailed regulation-by-regulation coverage |
| [Data Residency](data-residency.md) | Region controls and storage guarantees |
| [Audit Trail](audit-trail.md) | Immutable event log and retention policy |
| [GDPR Rights](gdpr-rights.md) | Data subject rights implementation |
| [Security Posture](security-posture.md) | Encryption, auth, and hardening |
| [Vulnerability Disclosure](vulnerability-disclosure.md) | How to report issues |

## Further Reading

- [Compliance Runs concept](../concepts/compliance-runs.md)
- [Governance concept](../concepts/governance.md)
- [Security Posture](security-posture.md)
