# JavaScript SDK Reference

The Meshant JavaScript/TypeScript SDK provides typed API wrappers for
integrating with the Meshant platform from Node.js and browser environments.

## Installation

```bash
npm install @datahub/interoperability-sdk
```

## Quick Start

```typescript
import { DataHubClient } from "@datahub/interoperability-sdk";

const client = new DataHubClient({
  baseUrl: "https://meshant-internal.example.com",
  apiKey: "msh_live_...",
});

// List assets
const assets = await client.assets.list({ page: 1, pageSize: 10 });
console.log(assets.results);

// Get a specific contract
const contract = await client.contracts.get("contract-uuid");
console.log(contract.name);
```

## Features

- **TypeScript-first** — full type definitions for all API responses
- **Authentication** — API key and JWT token support with automatic header injection
- **Retry logic** — exponential backoff for 5xx and 429 (rate limit) errors
- **Case transformation** — automatic `camelCase` ↔ `snake_case` conversion between JS and API conventions
- **Error handling** — typed exceptions (`DataHubError`, `NetworkError`, `UnauthorizedError`)

## API Modules

The client exposes the same API surface as the Python SDK:

| Module | Description |
|--------|-------------|
| `client.assets` | Asset CRUD, lifecycle transitions |
| `client.contracts` | Contract CRUD, validation, linting |
| `client.datasets` | Dataset CRUD, versioning |
| `client.files` | File upload, download |
| `client.dq` | Data quality runs |
| `client.compliance` | Compliance scanning |
| `client.search` | Full-text search |
| `client.marketplace` | Listings, orders, entitlements |
| `client.audit` | Audit event log |
| `client.webhooks` | Webhook management |
| `client.auth` | Authentication flows |

## Error Handling

```typescript
import { DataHubClient, DataHubError, UnauthorizedError } from "@datahub/interoperability-sdk";

try {
  const asset = await client.assets.get("non-existent-id");
} catch (error) {
  if (error instanceof UnauthorizedError) {
    console.error("Auth failed — check your API key");
  } else if (error instanceof DataHubError) {
    console.error(`API error ${error.statusCode}: ${error.message}`);
  }
}
```

## Development

```bash
cd sdk/js

# Install dependencies
npm install

# Build
npm run build

# Run tests
npm test

# Run with coverage
npm run test:unit
```

## Related

- [Python SDK Reference](../python/index.md) -- Python SDK documentation
- [Authentication](../../reference/authentication.md) -- API key and JWT setup
- [Error Codes](../../reference/error-codes.md) -- error code reference
