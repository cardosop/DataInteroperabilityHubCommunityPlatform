# External Developer

| Field | Value |
|-------|-------|
| Persona ID | DEV |
| Aliases | Partner Engineer, Platform Integrator, Solution Architect |
| RBAC Roles | `USER`, `INTEGRATION_DEVELOPER` (or tenant-specific API key) |
| Technical Level | High |
| Primary Journeys | JOURNEY-DE-001 (Contract-First Onboarding), general API/SDK integration |


## Who Is This Persona?

The External Developer builds systems that consume or extend Meshant
capabilities programmatically. This persona integrates Meshant's REST
API, Python SDK, or CLI into external applications -- data platforms,
analytics dashboards, ETL pipelines, or partner portals.

External Developers are highly technical. They read API specs, write
integration code, handle error responses, configure webhooks, and
navigate multi-tenancy and rate-limit constraints. They may never log
into the Meshant web UI; instead, they interact entirely through code.


## Goals

1. **Embed hub capabilities in external systems.** Use the API or SDK to
   list assets, trigger quality checks, run searches, and manage
   contracts from within external applications.

2. **Respect multi-tenancy and security boundaries.** Authenticate
   correctly, scope API calls to the appropriate tenant, and handle
   authorization errors gracefully.

3. **Stay within rate limits.** Understand and plan for per-tenant and
   per-endpoint rate limits. Implement exponential backoff and retry
   logic for 429 responses.

4. **Use the semantic layer for rich queries.** Leverage JSON-LD
   metadata and SPARQL queries to build knowledge-graph-driven
   integrations.

5. **React to platform events in real time.** Set up webhook receivers
   to process asset lifecycle events, DQ results, compliance scan
   outcomes, and billing events without polling.


## Key Concepts

- **Webhooks** -- Meshant pushes event notifications to registered HTTP
  endpoints. Webhooks support HMAC signature verification for security.
  See [Concepts: Webhooks](../../concepts/webhooks.md).

- **Search** -- Full-text and faceted search API across contracts, assets,
  and datasets. Supports filtering by domain, classification, quality
  status, and compliance status.
  See [Concepts: Search](../../concepts/search.md).

- **Semantic Resources** -- Assets and contracts are annotated with
  JSON-LD metadata conforming to Meshant's ontology. The SPARQL endpoint
  allows graph queries across the knowledge layer.
  See [Concepts: Semantic Resources](../../concepts/semantic-resources.md).

- **Jobs** -- Long-running operations (DQ checks, compliance scans,
  exports) are modeled as asynchronous jobs with status polling and
  webhook completion notifications.
  See [Concepts: Jobs](../../concepts/jobs.md).

- **MVP Feature Gating** -- Some API endpoints are gated behind the MVP
  boundary. Calling a post-MVP endpoint returns a structured
  `MVPGatedFeatureError` with a `FEATURE_GATED` error code and a message
  explaining the feature's roadmap status.


## What Can You Do?

### Authentication and Setup

| Task | Guide |
|------|-------|
| Obtain and manage API keys | [How-To: Authenticate and Authorize](how-to/authenticate-and-authorize.md) |
| Install the Python SDK | [Quickstart](quickstart.md) |
| Understand JWT scopes and permissions | [How-To: Authenticate and Authorize](how-to/authenticate-and-authorize.md) |

### Core Integration

| Task | Guide |
|------|-------|
| List and search assets via API | [Quickstart](quickstart.md) |
| Handle errors and MVP gating | [Quickstart](quickstart.md) |
| Set up webhook receivers | [How-To: Handle Webhooks](how-to/handle-webhooks.md) |

### Advanced Integration

| Task | Guide |
|------|-------|
| Query the semantic layer (SPARQL) | [How-To: Integrate Semantic Layer](how-to/integrate-semantic-layer.md) |
| Work with JSON-LD metadata | [How-To: Integrate Semantic Layer](how-to/integrate-semantic-layer.md) |
| Validate data with SHACL shapes | [How-To: Integrate Semantic Layer](how-to/integrate-semantic-layer.md) |


## Journeys

### JOURNEY-DE-001: Contract-First Onboarding (Shared with Data Engineer)

This journey is shared with the Data Engineer persona and represents the
programmatic path for onboarding assets:

1. **Define a data contract** specifying schema, quality SLAs, and
   compliance requirements.
2. **Register the asset** via API, referencing the contract.
3. **Upload or connect data** to the registered asset.
4. **Trigger DQ checks** and wait for results (poll or webhook).
5. **Publish** the asset to the marketplace once quality gates pass.

### General API Integration

A typical integration flow for an External Developer:

1. **Authenticate** -- obtain an API key or JWT token.
2. **Discover** -- search for assets matching criteria.
3. **Subscribe** -- set up webhooks for events of interest.
4. **Consume** -- pull data from asset endpoints or react to webhook
   events.
5. **Monitor** -- track API usage against rate limits and plan quotas.


## Rate Limits

Meshant enforces per-tenant rate limits to ensure fair platform usage:

| Tier | Requests/minute | Burst |
|------|----------------|-------|
| Free | 60 | 10 |
| Starter | 300 | 50 |
| Professional | 1,000 | 100 |
| Enterprise | 5,000 | 500 |

When rate-limited, the API returns HTTP 429 with a `Retry-After` header.
Always implement exponential backoff in your integration code.


## Error Handling

Meshant returns structured JSON error responses:

```json
{
  "error_code": "FEATURE_GATED",
  "message": "This feature is not available in the current MVP release.",
  "detail": "The mesh/ endpoint group is scheduled for post-MVP."
}
```

Common error codes relevant to External Developers:

| Code | HTTP Status | Meaning |
|------|-------------|---------|
| `AUTH_UNAUTHORIZED` | 401 | Missing or invalid token |
| `AUTH_FORBIDDEN` | 403 | Insufficient permissions for this tenant/resource |
| `NOT_FOUND` | 404 | Resource does not exist or is not accessible |
| `RATE_LIMITED` | 429 | Rate limit exceeded |
| `FEATURE_GATED` | 403 | Post-MVP feature not yet available |
| `VALIDATION_ERROR` | 400 | Invalid request parameters |


## Permissions

External Developers typically authenticate with API keys scoped to a
specific tenant. The key's permissions depend on the roles assigned to
the associated service account.

Minimum recommended roles:

- `USER` -- basic read access.
- `DATA_CONSUMER` -- access to marketplace and purchased assets.
- `INTEGRATION_DEVELOPER` -- webhook management and BaaS API keys.


## Next Steps

- [Quickstart: First API call in 5 minutes](quickstart.md)
- [Reference: All API, CLI, and SDK links](reference.md)
- [How-To Guides](how-to/)
