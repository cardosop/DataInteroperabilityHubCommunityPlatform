# Data Protection Officer (DPO)

> Also known as: Privacy Officer, Compliance Manager, GRC Analyst, Legal Counsel

## Who You Are

You are the guardian of regulatory compliance and data privacy within your
organization. You ensure that every dataset flowing through Meshant meets the
applicable regulatory requirements — GDPR, CCPA, HIPAA, or industry-specific
standards — before it is published internally or listed on the marketplace.

Typical job titles that map to this persona:

- Data Protection Officer (GDPR Article 37-39)
- Chief Privacy Officer / Privacy Manager
- Compliance Manager / GRC Analyst
- Information Governance Officer

## What You Care About

| Priority | Description |
|----------|-------------|
| Regulatory adherence | Datasets must pass compliance gates aligned to GDPR, CCPA, HIPAA. |
| PII detection | Automatically identify and classify sensitive data categories. |
| Audit trail | Immutable log of every action on every asset, exportable for regulators. |
| Risk assessment | Quantified risk levels (low / medium / high / critical) for each dataset. |
| Data subject rights | Support right-to-access, right-to-erasure, and portability requests. |
| Governance policies | Define and enforce organization-wide data handling policies. |

## Your MVP Capabilities

1. **Run compliance scans** — trigger automated scans that detect PII
   categories (email, phone, name, financial accounts, health data) and
   classify risk levels.
2. **Review compliance reports** — inspect per-column sensitivity
   classifications, risk scores, and recommended remediation actions.
3. **Export audit logs** — download complete, timestamped records of all
   actions for regulatory review.
4. **Configure GDPR data subject rights** — set up workflows for access
   requests, erasure requests, and data portability exports.
5. **Define governance policies** — create organization-level rules that
   gate asset publication based on compliance scan results.
6. **Monitor compliance posture** — dashboard view of compliant, at-risk,
   and non-compliant assets across the tenant.

## Key Journeys

- [Run a Compliance Scan](../../journeys/JOURNEY-DPO-001.md)
- [Review and Remediate High-Risk Findings](../../journeys/JOURNEY-DPO-006.md)
- [Export Audit Logs for Regulatory Review](../../journeys/JOURNEY-DPO-007.md)
- [Process a GDPR Erasure Request](../../journeys/JOURNEY-DPO-008.md)
- [Configure Governance Policies](../../journeys/JOURNEY-DPO-009.md)
- [Generate a Compliance Posture Report](../../journeys/JOURNEY-DPO-010.md)

## Typical Day

1. Open the **Compliance Dashboard** and review overnight scan results.
2. Drill into flagged assets — check which columns contain PII and whether
   masking or redaction is applied.
3. Coordinate with Data Engineers to remediate findings.
4. Process an incoming GDPR data subject access request.
5. Export the weekly audit log for the ongoing regulatory review.

## Related Concepts

- [Compliance Runs](../../concepts/compliance-runs.md) — automated PII detection and risk scoring
- [Audit Events](../../concepts/audit-events.md) — immutable action log
- [Governance Policies](../../concepts/governance.md) — organization-level rules
- [GDPR Rights](../../concepts/gdpr-rights.md) — data subject rights workflows

## Permissions and Roles

The DPO persona maps to the **AUDITOR** role in Meshant RBAC.
This role grants:

- Read access to all assets and their metadata (cross-domain).
- Execute permissions for compliance scans.
- Full access to audit event logs.
- Write access to governance policies.
- Execute permissions for GDPR data subject rights workflows.

## Get Started

- [5-Minute Quickstart](quickstart.md) — run your first compliance scan
- [How-To Guides](how-to/) — task-oriented guides for scans, audits, and GDPR
- [API / CLI / SDK Reference](reference.md) — endpoints and commands for compliance operations
