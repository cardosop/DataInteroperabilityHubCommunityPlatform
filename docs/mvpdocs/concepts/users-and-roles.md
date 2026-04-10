# Users and Roles

Users are the human (and service-account) identities that interact with Meshant. Every user authenticates through the platform's identity layer and is authorized by a role-based access control (RBAC) system that determines what actions they can perform within a given [tenant](tenants.md). A single person can hold different roles in different tenants, ensuring flexibility for consultants, auditors, and cross-functional teams.

Service accounts follow the same RBAC model as human users but authenticate via API keys rather than interactive login. This ensures that CI/CD pipelines and automated workflows are subject to the same permission boundaries.

## Lifecycle

| State | Description |
|---|---|
| `invited` | An invitation has been sent but not yet accepted. The user has no access until they complete onboarding. |
| `active` | The user has accepted the invitation and can log in. Their permissions are determined by their assigned roles. |
| `suspended` | A tenant-admin has suspended the user. Authentication is blocked but the account and audit history are preserved. |
| `deactivated` | The user has been permanently deactivated. They cannot log in, but their identity is retained in [audit events](audit-events.md) for traceability. |

Role assignments can change at any time without affecting the user's lifecycle state. Revoking all roles from an active user effectively makes them read-only on their own profile.

## Roles

| Role | Scope | Permissions |
|---|---|---|
| `viewer` | Tenant | Read-only access to assets, contracts, DQ results, and marketplace listings within the tenant. |
| `editor` | Tenant | Everything `viewer` can do, plus create/update assets, upload datasets, author contracts, and trigger DQ/compliance runs. |
| `admin` | Tenant | Everything `editor` can do, plus manage users, configure webhooks, and set governance policies for the tenant. |
| `tenant-admin` | Tenant | Full control over the tenant, including billing configuration, suspension of users, and tenant-level settings. |
| `platform-admin` | Platform | Cross-tenant administrative access. Can provision and decommission tenants, manage platform-wide settings, and view aggregated audit logs. |

Roles are additive. A user can hold multiple roles simultaneously (for example, `editor` in one domain and `admin` in another).

## Authentication

Meshant supports the following authentication methods:

| Method | Use Case | Details |
|---|---|---|
| Email + password | Interactive login for the web UI. | Passwords are hashed with bcrypt. Minimum 12 characters enforced. |
| API key | Service accounts and CLI authentication. | Keys are prefixed with `msh_` and scoped to a single tenant. |
| OAuth 2.0 / OIDC | External identity provider integration. | Authorization code flow with PKCE for web clients, client credentials for services. |

API keys have configurable expiration (default: 90 days) and can be rotated without downtime using a dual-key overlap period. Key creation and rotation events are recorded in the [audit log](audit-events.md).

## Session and Token Management

Interactive sessions use short-lived JWTs (15-minute access tokens) with longer-lived refresh tokens (7 days). Token refresh is transparent to the user. Sessions can be revoked by the user or by a `tenant-admin` through the user management API.

## Relationships

- **Tenants** -- Users exist within [tenants](tenants.md). A user's role assignments are always scoped to a specific tenant. Platform-admins are the exception, operating across all tenants.
- **Audit Events** -- Every action a user takes is recorded in the [audit log](audit-events.md), including the user ID, role at the time of action, and the affected resource.
- **Assets** -- Users with the `editor` role or above own and manage [assets](assets.md). Ownership is tracked for accountability and lineage attribution.
- **Governance** -- [Governance](governance.md) policies can restrict which roles are allowed to perform certain operations (for example, only `admin` can publish to the Marketplace).
- **Webhooks** -- Only users with `admin` or `tenant-admin` roles can create and manage [webhook](webhooks.md) configurations.
- **Billing** -- [Billing](billing.md) management is restricted to `tenant-admin` and `platform-admin` roles.

## MVP Scope

**Available at launch:**

- User invitation and onboarding flow via API and CLI.
- Five built-in roles: viewer, editor, admin, tenant-admin, platform-admin.
- Role assignment and revocation per tenant.
- Service account creation with API key authentication.
- API key rotation and expiration management.
- User listing, filtering by role and status.
- Suspension and deactivation of user accounts.

**Post-MVP:**

- Custom role definitions with fine-grained permission sets.
- Attribute-based access control (ABAC) for column-level and row-level restrictions.
- SSO integration (SAML 2.0, OIDC).
- Multi-factor authentication enforcement per tenant.
- User groups for bulk role assignment.
- Temporary elevated access with automatic expiry.

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Invite user | `POST /api/v1/users/invite` | `meshant user invite <email>` | `client.users.invite(email)` |
| Get user | `GET /api/v1/users/{id}` | `meshant user get <id>` | `client.users.get(id)` |
| List users | `GET /api/v1/users` | `meshant user list` | `client.users.list()` |
| Assign role | `POST /api/v1/users/{id}/roles` | `meshant user assign-role <id> <role>` | `client.users.assign_role(id, role)` |
| Revoke role | `DELETE /api/v1/users/{id}/roles/{role}` | `meshant user revoke-role <id> <role>` | `client.users.revoke_role(id, role)` |
| Suspend user | `POST /api/v1/users/{id}/suspend` | `meshant user suspend <id>` | `client.users.suspend(id)` |
| Create service account | `POST /api/v1/service-accounts` | `meshant service-account create` | `client.service_accounts.create()` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for invitation parameters and role definitions.
