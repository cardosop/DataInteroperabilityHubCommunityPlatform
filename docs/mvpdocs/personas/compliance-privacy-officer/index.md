# Compliance & Privacy Officer (CPO)

> Also known as: Data Protection Officer (DPO), Privacy Officer, Compliance Manager, GRC Analyst

## Who You Are

You are the guardian of regulatory compliance and data privacy within your
organization. Your role sits at the intersection of legal, risk management,
and data operations. You ensure that every dataset flowing through Meshant
meets the applicable regulatory requirements -- GDPR, CCPA, HIPAA, or
industry-specific standards -- before it is published internally or listed
on the marketplace.

You may not write code daily, but you need clear dashboards, exportable
audit logs, and the ability to trigger compliance scans without engineering
support.

Typical job titles that map to this persona:

- Data Protection Officer
- Chief Privacy Officer / Privacy Manager
- Compliance Manager / GRC Analyst
- Information Governance Officer

## What You Care About

| Priority | Description |
|----------|-------------|
| Regulatory adherence | Datasets must pass compliance gates aligned to GDPR, CCPA, HIPAA. |
| PII detection | Automatically identify and classify sensitive data categories. |
| Audit trail | Immutable log of every action on every asset, exportable for regulators. |
| Risk assessment | Quantified risk levels (low / medium / high) for each dataset. |
| Data subject rights | Support right-to-access, right-to-erasure, and portability requests. |
| Governance policies | Define and enforce organization-wide data handling policies. |

## Your MVP Capabilities

Within the Meshant MVP you can:

1. **Run compliance scans** -- trigger automated scans that detect PII
   categories (email, phone, name, date of birth, financial accounts) and
   classify risk level.

2. **Review compliance reports** -- inspect per-column sensitivity
   classifications, risk scores, and recommended remediation actions.

3. **Export audit logs** -- download a complete, timestamped record of all
   actions performed on assets, contracts, and marketplace listings.

4. **Configure GDPR data subject rights** -- set up workflows for access
   requests, erasure requests, and data portability exports.

5. **Define governance policies** -- create organization-level rules that
   gate asset publication based on compliance scan results.

6. **Monitor compliance posture** -- dashboard view of how many assets are
   compliant, at risk, or non-compliant across all domains.

## Key Journeys

Step-by-step walkthroughs for your core workflows:

- [Run a Compliance Scan on a New Asset](../../journeys/JOURNEY-CPO-001.md)
- [Review and Remediate High-Risk Findings](../../journeys/JOURNEY-CPO-006.md)
- [Export Audit Logs for a Regulatory Review](../../journeys/JOURNEY-CPO-007.md)
- [Process a GDPR Erasure Request](../../journeys/JOURNEY-CPO-008.md)
- [Configure Governance Policies](../../journeys/JOURNEY-CPO-009.md)
- [Generate a Compliance Posture Report](../../journeys/JOURNEY-CPO-010.md)

## Typical Day

1. Open the **Compliance Dashboard** and review the overnight scan results.
   Filter for any assets that moved to `high` risk.
2. Drill into a flagged asset -- check which columns contain PII and whether
   masking or redaction is already applied.
3. Coordinate with the Data Product Owner to remediate findings (mask email
   columns, remove direct identifiers, etc.).
4. Process an incoming GDPR data subject access request: search for the
   subject's data across all assets, generate the export, and record the
   action in the audit log.
5. Export the weekly audit log and share it with the legal team for the
   ongoing regulatory review.

## Related Concepts

- [Compliance Runs](../../concepts/compliance-runs.md) -- automated PII detection and risk scoring
- [Audit Events](../../concepts/audit-events.md) -- immutable action log
- [Governance Policies](../../concepts/governance.md) -- organization-level rules
- [GDPR Rights](../../concepts/gdpr-rights.md) -- data subject rights workflows

## Sensitivity Categories

Meshant detects the following categories during a compliance scan:

| Category Code | Description | Risk Weight |
|--------------|-------------|-------------|
| PII_DIRECT_EMAIL | Email addresses | High |
| PII_DIRECT_PHONE | Phone numbers | High |
| PII_DIRECT_NAME | Full or partial names | High |
| PII_QUASI_DOB | Dates of birth | Medium |
| PII_QUASI_ZIP | Postal / ZIP codes | Medium |
| PII_QUASI_GENDER | Gender indicators | Low |
| FINANCIAL_ACCOUNT | Bank / credit card numbers | High |
| HEALTH_CONDITION | Medical conditions or diagnoses | High |

## Permissions and Roles

The CPO persona maps to the **compliance_officer** role in Meshant RBAC.
This role grants:

- Read access to all assets and their metadata (cross-domain).
- Execute permissions for compliance scans.
- Full access to audit event logs.
- Write access to governance policies.
- Execute permissions for GDPR data subject rights workflows.

## Get Started

- [5-Minute Quickstart](quickstart.md) -- run your first compliance scan
- [How-To Guides](how-to/) -- task-oriented guides for scans, audits, and GDPR
- [API / CLI / SDK Reference](reference.md) -- endpoints and commands for compliance operations
