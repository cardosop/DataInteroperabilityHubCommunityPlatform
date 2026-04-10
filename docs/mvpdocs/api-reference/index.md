# Meshant API Reference

This section documents every REST API exposed by the Meshant platform.
All endpoints follow consistent conventions for authentication, pagination,
and error handling described in the [Reference](../reference/) section.

## Base URL

| Environment | Base URL |
|-------------|----------|
| Production  | `https://meshant-internal.example.com/api/v1/` |
| Staging     | `https://meshant-internal.example.com/api/v1/` |

## API Apps

| App | Base Path | Description |
|-----|-----------|-------------|
| [Authentication](auth.md) | `/api/v1/auth/` | Login, logout, token refresh, email verification, password reset |
| [Tenants](tenants.md) | `/api/v1/tenants/` | Multi-tenancy management, member invitations, context switching |
| [Users](users.md) | `/api/v1/users/` | User CRUD, role assignment, permissions, profile management |
| [Audit](audit.md) | `/api/v1/audit/` | Audit event logging, filtering, and export |
| [Files](files.md) | `/api/v1/files/` | File upload, download, listing, and deletion |
| [Datasets](datasets.md) | `/api/v1/datasets/` | Dataset creation, schema inference, validation |
| [Jobs](jobs.md) | `/api/v1/jobs/` | Background job tracking, status checks, cancellation |
| [Contracts](contracts.md) | `/api/v1/contracts/` | Data contract authoring, validation, linting, versioning |
| [Assets](assets.md) | `/api/v1/assets/` | Data asset lifecycle (data-first and contract-first flows) |
| [Data Quality](dq.md) | `/api/v1/dq/` | Data quality checks, profiling, result retrieval |
| [Compliance](compliance.md) | `/api/v1/compliance/` | Compliance scanning, PII detection, finding review |
| [Semantic](semantic.md) | `/api/v1/semantic/` | Semantic URI resolution, SPARQL queries, JSON-LD contexts |
| [Marketplace](marketplace.md) | `/api/v1/marketplace/` | Data product listings, orders, entitlements |
| [Search](search.md) | `/api/v1/search/` | Full-text search, faceted filtering, autocomplete |
| [Developer](developer.md) | `/api/v1/developer/` | API key management, rate limits, usage statistics |
| [Webhooks](webhooks.md) | `/api/v1/webhooks/` | Webhook registration, testing, delivery logs |
| [Governance](governance.md) | `/api/v1/governance/` | Policy management, retention rules, consent, GDPR rights |
| [Billing](billing.md) | `/api/v1/billing/` | Subscriptions, invoices, usage metering, quotas |
| [Platform](platform.md) | `/api/v1/platform/` | Platform configuration, health checks, feature flags |

## Common Conventions

- **Authentication** -- All endpoints (except `auth/login/` and `auth/verify-email/`)
  require a valid JWT bearer token or API key. See [Authentication](../reference/authentication.md).
- **Pagination** -- List endpoints accept `page` and `page_size` query parameters.
  Default page size is 20; maximum is 100.
- **Filtering** -- Most list endpoints support query-parameter filters documented
  on each page.
- **Error format** -- Errors return a JSON body with `code`, `message`, and
  optional `details`. See [Error Codes](../reference/error-codes.md).
- **Rate limiting** -- Responses include `X-RateLimit-Limit`,
  `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers.
