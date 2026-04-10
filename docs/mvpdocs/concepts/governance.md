# Governance

Governance in Meshant is the policy framework that automates and enforces data management rules across a [tenant](tenants.md). It encompasses compliance policies, retention rules, consent tracking, access controls, and regulatory rights management (GDPR, CCPA). Governance policies act as guardrails that prevent non-compliant data from being published, shared, or retained beyond its allowed lifetime.

Policies are defined by tenant administrators and enforced automatically by the platform. When a policy is violated, the offending operation is blocked and an [audit event](audit-events.md) is recorded. This ensures that governance is not advisory but actively enforced in the data lifecycle.

## Lifecycle

Governance policies have their own lifecycle:

| State | Description |
|---|---|
| `draft` | The policy is being authored. It is not enforced. |
| `active` | The policy is enforced on all applicable resources within the tenant. |
| `testing` | The policy evaluates resources but does not block violations. Results are logged for review. |
| `retired` | The policy is no longer enforced. It is retained for historical audit reference. |

The `testing` state is important for rolling out new policies safely. Teams can observe the impact of a policy before activating enforcement.

## Policy Types

| Type | Description |
|---|---|
| Quality gate | Minimum [DQ score](dq-runs.md) required before an asset can be published. Configurable threshold per domain. |
| Compliance threshold | Maximum [risk level](compliance-runs.md) allowed for published assets. For example, "no asset with `critical` risk may be listed on the Marketplace." |
| Retention policy | Maximum data retention period. Assets and datasets older than the policy limit are flagged for archival or deletion. |
| Contract requirement | Every published asset must have at least one active [contract](contracts.md). |
| Lineage completeness | Assets must have documented [lineage](lineage.md) before they can transition to `active` or `published`. |
| Consent tracking | Data subjects' consent status is tracked. Assets containing personal data must reference a valid consent basis. |
| Access restriction | Restricts access to specific assets based on compliance classification (e.g., `critical` risk assets accessible only to `admin` roles). |

## GDPR Rights Management

Meshant provides built-in support for data subject rights under GDPR:

| Right | Platform Support |
|---|---|
| Right of access | Data subject access requests generate a report listing all assets containing the subject's data, identified through [compliance runs](compliance-runs.md). |
| Right to erasure | Erasure requests trigger a workflow that identifies and removes or anonymizes the subject's data across all relevant assets. |
| Right to rectification | Rectification requests are routed to the asset owner with the specific fields requiring correction. |
| Right to portability | Export requests generate a machine-readable extract of the subject's data in a standard format. |

All rights management actions are recorded as [audit events](audit-events.md) with full traceability.

## Relationships

- **Compliance Runs** -- [Compliance runs](compliance-runs.md) produce the risk assessments that governance policies evaluate.
- **DQ Runs** -- [DQ runs](dq-runs.md) produce the quality scores that quality gate policies enforce.
- **Audit Events** -- Policy violations, enforcement actions, and GDPR requests are all logged as [audit events](audit-events.md).
- **Assets** -- [Assets](assets.md) are the primary resources that governance policies govern. Publication, sharing, and retention are all controlled.
- **Contracts** -- [Contracts](contracts.md) are required by contract-requirement policies and provide the quality rule definitions.
- **Tenants** -- Governance policies are scoped to a [tenant](tenants.md). Each tenant defines its own policy set.
- **Users and Roles** -- Only `admin` and `tenant-admin` [roles](users-and-roles.md) can create and manage governance policies.
- **Marketplace Listings** -- [Marketplace listings](marketplace-listings.md) are subject to quality gate and compliance threshold policies.

## MVP Scope

**Available at launch:**

- Policy authoring via API and CLI.
- Quality gate policies with configurable score thresholds.
- Compliance threshold policies with risk level limits.
- Retention policies with automatic flagging of over-age assets.
- Contract requirement enforcement for published assets.
- Policy testing mode for safe rollout.
- Policy violation audit logging.
- GDPR right-of-access request workflow.
- GDPR right-to-erasure request workflow.

**Post-MVP:**

- Visual policy editor in the web UI.
- Policy templates for common regulatory frameworks (GDPR, CCPA, HIPAA, SOC 2).
- Automated policy recommendations based on tenant data profile.
- Cross-tenant policy inheritance for enterprise groups.
- Policy impact simulation (what would happen if this policy were activated).
- Consent management dashboard with subject tracking.
- Automated regulatory reporting (GDPR Article 30 records of processing).

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Create policy | `POST /api/v1/governance/policies` | `meshant governance create-policy` | `client.governance.create_policy()` |
| Get policy | `GET /api/v1/governance/policies/{id}` | `meshant governance get-policy <id>` | `client.governance.get_policy(id)` |
| List policies | `GET /api/v1/governance/policies` | `meshant governance list-policies` | `client.governance.list_policies()` |
| Activate policy | `POST /api/v1/governance/policies/{id}/activate` | `meshant governance activate <id>` | `client.governance.activate(id)` |
| Submit GDPR request | `POST /api/v1/governance/gdpr-requests` | `meshant governance gdpr-request` | `client.governance.gdpr_request()` |
| List GDPR requests | `GET /api/v1/governance/gdpr-requests` | `meshant governance gdpr-list` | `client.governance.gdpr_list()` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for policy definition schemas and GDPR request workflows.
