# Supported Regulations

Meshant includes built-in rule sets for five major regulatory frameworks. Each
rule set defines the checks that [compliance runs](../concepts/compliance-runs.md)
execute against [assets](../concepts/assets.md) before they may be published or
shared.

Regulations are assigned at the [tenant](../concepts/tenants.md) level. A single
tenant may be subject to multiple regulations simultaneously (for example, a
healthcare company operating in the EU would enable both GDPR and HIPAA).

---

## GDPR

**General Data Protection Regulation -- European Union**

| Aspect | Detail |
|---|---|
| Scope | Any processing of personal data of EU residents |
| Key requirements | Lawful basis for processing, data minimization, purpose limitation, data subject rights, breach notification within 72 hours |
| Meshant coverage | PII detection classifiers flag personal data fields. Consent records are tracked per data subject. Right to access, erasure, portability, and rectification workflows are built in. Audit trail captures every access event for accountability. Data residency controls ensure data stays within approved regions. |

See [GDPR Rights](gdpr-rights.md) for the full data-subject-rights implementation.

---

## HIPAA

**Health Insurance Portability and Accountability Act -- United States**

| Aspect | Detail |
|---|---|
| Scope | Protected Health Information (PHI) held by covered entities and business associates |
| Key requirements | Administrative, physical, and technical safeguards; minimum necessary standard; breach notification; Business Associate Agreements |
| Meshant coverage | PHI classifiers detect health-related identifiers (MRN, SSN, diagnosis codes). Encryption at rest (AES-256) and in transit (TLS 1.3) satisfy the technical safeguard requirement. Role-based access control enforces the minimum necessary standard. Immutable audit logs provide the activity review required by the Security Rule. |

---

## SOX

**Sarbanes-Oxley Act -- United States (financial reporting)**

| Aspect | Detail |
|---|---|
| Scope | Internal controls over financial reporting for publicly traded companies |
| Key requirements | Segregation of duties, change management controls, audit trail for financial data modifications |
| Meshant coverage | RBAC policies enforce segregation of duties by preventing a single user from both authoring and approving data contracts. Every schema change and data mutation is logged with the acting user, timestamp, and before/after values. Compliance runs verify that financial datasets have not been modified outside approved workflows. |

---

## LGPD

**Lei Geral de Protecao de Dados -- Brazil**

| Aspect | Detail |
|---|---|
| Scope | Processing of personal data of individuals located in Brazil |
| Key requirements | Legal basis for processing, data subject rights (similar to GDPR), Data Protection Officer appointment, cross-border transfer restrictions |
| Meshant coverage | The same PII detection and consent-tracking mechanisms used for GDPR apply to LGPD. Data residency controls can restrict Brazilian data to approved regions. The audit trail satisfies the LGPD accountability principle by recording all processing activities. |

---

## CCPA

**California Consumer Privacy Act -- California, United States**

| Aspect | Detail |
|---|---|
| Scope | Personal information of California residents collected by qualifying businesses |
| Key requirements | Right to know, right to delete, right to opt out of sale, non-discrimination |
| Meshant coverage | PII classifiers identify California-resident data. The right-to-delete workflow mirrors the GDPR erasure flow. Opt-out-of-sale flags are tracked at the consent level and enforced by compliance runs before any marketplace listing. Audit logs record all consumer requests and platform responses. |

---

## Regulation Assignment

Regulations are configured in the tenant settings:

```json
PATCH /api/v1/tenants/{tenant_id}
{
  "compliance_regulations": ["gdpr", "hipaa"]
}
```

Once assigned, every new [compliance run](../concepts/compliance-runs.md) for that
tenant will include the rule sets of all assigned regulations. Removing a
regulation does not delete historical compliance results; those remain in the
[audit trail](audit-trail.md) for the configured retention period.

## Further Reading

- [Compliance Runs concept](../concepts/compliance-runs.md)
- [Governance concept](../concepts/governance.md)
- [Data Residency](data-residency.md)
- [Audit Trail](audit-trail.md)
