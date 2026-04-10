# Marketplace & Platform Admin

| Field | Value |
|-------|-------|
| Persona ID | MPA |
| Aliases | Platform Owner, Operations Lead, Business Owner |
| RBAC Roles | `USER`, `TENANT_ADMIN`, `is_staff=true` |
| Technical Level | Medium |
| Primary Journeys | JOURNEY-PA-001 (Onboard Marketplace Instance), JOURNEY-MPA-005 (Marketplace Admin), JOURNEY-TA-007 (Monitor Cost Tracking), JOURNEY-TA-008 (Configure Integration Ecosystem) |


## Who Is This Persona?

The Marketplace & Platform Admin (MPA) is responsible for the operational
health and commercial success of the Meshant platform. This persona
manages tenants, configures platform-wide defaults, monitors marketplace
activity, and ensures the trust layer (data quality, compliance, billing)
functions correctly.

MPAs typically combine business acumen with enough technical literacy to
navigate admin dashboards, interpret metrics, and configure thresholds.
They do not write code but may use the CLI for bulk operations or
troubleshooting.


## Goals

1. **Grow marketplace supply and demand.** Onboard new tenants, approve
   data providers, and ensure a healthy ratio of listings to consumers.

2. **Maintain platform trust.** Configure default data quality profiles
   and compliance thresholds so that every listing meets a baseline
   standard before it is visible to consumers.

3. **Ensure accurate billing.** Monitor usage across tenants, reconcile
   invoices, handle billing disputes, and manage plan tier assignments.

4. **Govern the platform.** Enforce naming conventions, domain
   taxonomies, role assignments, and audit trail retention policies
   across all tenants.

5. **Track operational KPIs.** Monitor revenue, asset counts, SLA
   compliance, onboarding velocity, and support ticket volume.


## Key Concepts

- **Tenants** -- Each organization on Meshant is a tenant. Tenants are
  isolated by default (multi-tenancy). The MPA manages tenant lifecycle:
  creation, KYC approval, suspension, and deactivation.
  See [Concepts: Tenants](../../concepts/tenants.md).

- **Users and Roles** -- Each tenant has users with RBAC roles (`USER`,
  `DATA_PROVIDER`, `DATA_CONSUMER`, `TENANT_ADMIN`, etc.). The MPA can
  view cross-tenant user lists and escalate role changes.
  See [Concepts: Users and Roles](../../concepts/users-and-roles.md).

- **Billing** -- Platform-level billing configuration includes plan tiers,
  usage quotas, pricing rules, and invoice generation. The MPA reviews
  cross-tenant billing dashboards.
  See [Concepts: Billing](../../concepts/billing.md).

- **Governance** -- Platform-wide governance rules include default DQ
  profiles, compliance scan schedules, retention policies, and domain
  taxonomies.
  See [Concepts: Governance](../../concepts/governance.md).


## What Can You Do?

### Tenant Management

| Task | Guide |
|------|-------|
| Review and approve tenant KYC applications | [How-To: Onboard Tenant](how-to/onboard-tenant.md) |
| Suspend or deactivate a tenant | [How-To: Onboard Tenant](how-to/onboard-tenant.md) |
| View cross-tenant user lists | Django Admin panel |

### Platform Configuration

| Task | Guide |
|------|-------|
| Set default DQ profiles for new assets | [How-To: Configure Platform Defaults](how-to/configure-platform-defaults.md) |
| Set compliance scan thresholds | [How-To: Configure Platform Defaults](how-to/configure-platform-defaults.md) |
| Manage domain taxonomy | [How-To: Configure Platform Defaults](how-to/configure-platform-defaults.md) |

### Monitoring and Reporting

| Task | Guide |
|------|-------|
| Track marketplace revenue and growth | [How-To: Monitor Marketplace Metrics](how-to/monitor-marketplace-metrics.md) |
| Review SLA compliance across tenants | [How-To: Monitor Marketplace Metrics](how-to/monitor-marketplace-metrics.md) |
| Audit platform activity | Audit log in Django Admin |


## Journeys

### JOURNEY-PA-001: Onboard Marketplace Instance

Initial platform setup performed once per deployment:

1. **Configure platform identity** -- name, logo, domain, support email.
2. **Set billing defaults** -- plan tiers, trial periods, payment methods.
3. **Define governance baselines** -- default DQ profiles, compliance
   scan schedules, retention policies.
4. **Create the first tenant** (typically the platform operator's own
   organization).
5. **Invite initial users** and assign roles.

### JOURNEY-MPA-005: Marketplace Admin Operations

Ongoing operational duties:

1. **Review pending KYC applications** and approve or reject.
2. **Monitor marketplace metrics** -- revenue, listings, active consumers.
3. **Handle escalations** -- billing disputes, compliance violations,
   tenant suspension requests.

### JOURNEY-TA-007: Monitor Cost Tracking

1. **Open the billing dashboard** with the cross-tenant view.
2. **Review per-tenant usage** against plan limits.
3. **Identify tenants approaching quota** and notify or auto-upgrade.
4. **Reconcile invoices** against payment processor records.

### JOURNEY-TA-008: Configure Integration Ecosystem

1. **Review available marketplace integrations** (Snowflake, AWS Data
   Exchange, Databricks, etc.).
2. **Enable or disable integrations** at the platform level.
3. **Set default sync schedules** for enabled integrations.


## Permissions

The MPA requires `TENANT_ADMIN` and `is_staff=true`, which grants:

- Full Django Admin panel access.
- Cross-tenant read access to users, assets, billing, and audit logs.
- Ability to approve, suspend, or deactivate tenants.
- Ability to configure platform-wide defaults (DQ, compliance, billing).

The MPA does **not** typically:

- Publish or manage individual data assets (that is the DPO's job).
- Write CLI scripts or SDK integrations (that is the DE's or DEV's job).
- Run compliance scans on individual assets (that is the CPO's job).


## Next Steps

- [Quickstart: First admin tasks](quickstart.md)
- [Reference: API, CLI, and SDK links](reference.md)
- [How-To Guides](how-to/)
