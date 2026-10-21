# Tenants

A tenant is the top-level isolation boundary in Meshant. Every organization that uses the platform operates within its own tenant, which provides complete separation of data, users, configuration, and billing. Tenants ensure that one organization's assets, contracts, and governance policies never leak into another's namespace.

Tenant provisioning creates the storage buckets, database schemas, search indexes, and IAM bindings required for the organization. The platform supports both self-service sign-up (with approval workflow) and operator-provisioned tenants for enterprise deployments.

## Lifecycle

| State | Description |
|---|---|
| `provisioning` | Infrastructure is being created. Storage, database schemas, and default configuration are being set up. |
| `active` | The tenant is fully operational. Users can log in, upload data, and use all platform features. |
| `suspended` | The tenant has been suspended due to billing issues or policy violations. Read-only access is maintained for data export. |
| `decommissioning` | An admin has requested tenant deletion. Data is being exported and purged according to retention policy. |
| `deleted` | All data has been purged. The tenant ID is reserved for 90 days to prevent accidental re-use. |

Transitions between states are restricted to platform administrators except for the `active` to `suspended` transition, which can be triggered automatically by the [billing](billing.md) system when invoices are overdue beyond the grace period.

## Tenant Configuration

Each tenant carries a configuration object that controls platform behavior within its boundary:

| Setting | Default | Description |
|---|---|---|
| `storage_quota_gb` | 100 | Maximum data storage in GB across all datasets. |
| `max_concurrent_jobs` | 10 | Maximum number of [jobs](jobs.md) that can run simultaneously. |
| `dq_score_threshold` | 70 | Minimum [DQ score](dq-runs.md) required to publish an asset. |
| `compliance_risk_max` | `high` | Maximum [compliance risk level](compliance-runs.md) allowed for published assets. |
| `retention_days` | 365 | Default data retention period in days before archival flagging. |
| `api_rate_limit` | 1000 | Maximum API requests per minute. |
| `webhook_max_endpoints` | 20 | Maximum number of [webhook](webhooks.md) endpoints per tenant. |

Configuration changes are recorded as [audit events](audit-events.md) and take effect immediately.

## Isolation Model

Tenant isolation is enforced at multiple layers:

- **Middleware** -- `TenantSuspensionMiddleware` resolves the tenant from the
  request (header, user, or database lookup) and blocks writes for suspended
  or deleted tenants. Subscription status is also checked — overdue
  subscriptions trigger read-only mode.
- **Queryset filtering** -- All viewsets and services filter querysets by the
  resolved `tenant_id`. Most models have a required `tenant` foreign key. A
  few models are **platform-scoped** (nullable tenant) for system-level data:

  | Model | Tenant FK | Reason |
  |-------|-----------|--------|
  | `AuditEvent` | Nullable | Platform-level events (e.g., tenant creation) |
  | `User` | Nullable | Platform admins exist outside any single tenant |
  | `Event` | Nullable | System events without tenant context |
  | `SecurityAuditLog` | Nullable | Cross-tenant security monitoring |
  | `Contract`, `Asset`, `Dataset` | **Required** | Always tenant-scoped |

- **Storage** -- File upload paths include the tenant ID. Access is enforced at
  the application layer (pre-signed URLs are scoped to the tenant's prefix).
- **Search** -- [Search](search.md) indexes include `tenant_id` in the tsvector
  filter. Queries always include a tenant predicate.
- **API requests** -- All authenticated requests must include a valid tenant
  context. Requests without tenant context receive empty results (not 403) to
  avoid disclosing resource existence across tenants.

## Relationships

- **Users and Roles** -- Each tenant has its own set of [users and roles](users-and-roles.md). A user can belong to multiple tenants but has independent role assignments in each.
- **Assets** -- All [assets](assets.md), [datasets](datasets.md), and [contracts](contracts.md) are scoped to a tenant. Cross-tenant asset discovery happens only through the [Marketplace](marketplace-listings.md).
- **Billing** -- Each tenant has its own [billing](billing.md) account, usage tracking, quotas, and invoicing. The billing state directly influences the tenant lifecycle (overdue payments trigger suspension).
- **Governance** -- [Governance](governance.md) policies are defined per tenant. Each tenant can customize retention periods, compliance thresholds, and approval workflows.
- **Audit Events** -- [Audit events](audit-events.md) are partitioned by tenant. Each tenant's audit log is independent and subject to the tenant's retention policy.
- **Webhooks** -- [Webhook](webhooks.md) configurations are tenant-scoped. Each tenant manages its own notification endpoints.
- **Search** -- [Search](search.md) indexes are tenant-isolated. A search query in one tenant never returns results from another tenant (marketplace search is a separate index).

## MVP Scope

**Available at launch:**

- Operator-provisioned tenants via API.
- Tenant-level configuration: storage quotas, DQ thresholds, compliance risk tolerance.
- Role-based access within each tenant (viewer, editor, admin, tenant-admin).
- Tenant suspension and reactivation.
- Tenant usage dashboard showing asset counts, storage consumed, and API call volume.
- Multi-tenant search isolation.

**Post-MVP:**

- Self-service tenant sign-up with approval workflow.
- Tenant federation for enterprise groups (parent/child tenant hierarchies).
- Custom domain mapping per tenant.
- Tenant-level SSO/SAML configuration.
- Cross-tenant data sharing agreements with governance controls.
- Tenant cloning for staging/development environments.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Create tenant | `POST /api/v1/tenants` | `meshant tenant create` | `client.tenants.create()` |
| Get tenant | `GET /api/v1/tenants/{id}` | `meshant tenant get <id>` | `client.tenants.get(id)` |
| List tenants | `GET /api/v1/tenants` | `meshant tenant list` | `client.tenants.list()` |
| Update config | `PATCH /api/v1/tenants/{id}` | `meshant tenant update <id>` | `client.tenants.update(id)` |
| Suspend tenant | `POST /api/v1/tenants/{id}/suspend` | `meshant tenant suspend <id>` | `client.tenants.suspend(id)` |
| Reactivate tenant | `POST /api/v1/tenants/{id}/reactivate` | `meshant tenant reactivate <id>` | `client.tenants.reactivate(id)` |
| Delete tenant | `DELETE /api/v1/tenants/{id}` | `meshant tenant delete <id>` | `client.tenants.delete(id)` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for configuration options and quota parameters.
