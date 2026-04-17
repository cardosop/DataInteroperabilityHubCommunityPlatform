# GraphQL API

Meshant exposes a GraphQL endpoint alongside the primary REST API. GraphQL
is suited for UI aggregation, mobile apps, and complex queries that would
require multiple REST calls.

## Endpoint

| URL | Framework | Auth |
|-----|-----------|------|
| `/graphql-graphene/` | Graphene-Django | JWT or API key (same as REST) |

## Schema

The GraphQL schema exposes the same domain objects as the REST API:

- **Queries**: assets, contracts, datasets, tenants, users, jobs
- **Filtering**: built-in field filters on most types
- **Pagination**: Relay-style cursor pagination
- **Tenant isolation**: automatic -- queries are scoped to the authenticated tenant

## Example Query

```graphql
query {
  assets(first: 10, status: "active") {
    edges {
      node {
        id
        name
        status
        contract {
          id
          name
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

## When to Use GraphQL vs REST

| Use Case | Recommended |
|----------|-------------|
| Simple CRUD | REST |
| File uploads | REST |
| UI dashboards (multiple related entities) | GraphQL |
| Mobile apps (minimal payload) | GraphQL |
| Webhook integrations | REST |
| CLI / SDK automation | REST |

## Limitations

- **MVP scope**: GraphQL is available but not the primary API surface. REST
  endpoints have richer feature coverage (validation, linting, export, etc.).
- **Mutations**: read-heavy; write operations should use REST endpoints.
- **Query complexity**: depth and node limits are enforced to prevent abuse.

## WebSocket Support

Real-time updates are available via Django Channels (WebSocket). The frontend
connects on login and falls back to HTTP polling when WebSocket is unavailable.

Event types delivered via WebSocket:

- Asset status changes
- Contract validation results
- DQ run completions
- Compliance scan results
- Job status updates

## Related

- [REST API Reference](index.md) -- primary API documentation
- [Webhooks](webhooks.md) -- event subscriptions via HTTP callbacks
- [Authentication](../reference/authentication.md) -- JWT and API key auth
