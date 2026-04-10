# How-To: Authenticate and Authorize

This guide covers the authentication and authorization mechanisms
available to External Developers integrating with the Meshant API.


## Authentication Methods

Meshant supports two authentication methods for API access:

### 1. API Keys

API keys are the simplest method and are recommended for server-to-server
integrations.

**Creating an API key:**

1. Log in to the Meshant web UI.
2. Navigate to **Settings > API Keys**.
3. Click **Create API Key**.
4. Name the key descriptively (e.g., `analytics-pipeline-prod`).
5. Select the required **scopes** (see below).
6. Copy the key immediately -- it is shown only once.

**Using the key in requests:**

```bash
curl -H "Authorization: Api-Key YOUR_KEY_HERE" \
  https://meshant-internal.example.com/api/v1/assets/
```

In the SDK:

```python
from datahub_interoperability import DataHubClient, DataHubClientConfig

client = DataHubClient(config=DataHubClientConfig(
    base_url="https://meshant-internal.example.com",
    api_key="YOUR_KEY_HERE",
))
```

Or set environment variables and use `DataHubClient.from_env()`:

```bash
export DATAHUB_API_KEY="YOUR_KEY_HERE"
export DATAHUB_BASE_URL="https://meshant-internal.example.com"
```

### 2. JWT Tokens

JWT tokens are used for user-context integrations (e.g., a frontend app
acting on behalf of a logged-in user).

**Obtaining a token:**

```bash
curl -X POST https://meshant-internal.example.com/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "secret"}'
```

Response:

```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

**Using the token:**

```bash
curl -H "Authorization: Bearer eyJ..." \
  https://meshant-internal.example.com/api/v1/assets/
```

**Refreshing an expired token:**

```bash
curl -X POST https://meshant-internal.example.com/api/v1/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "eyJ..."}'
```


## Scopes

API keys and JWT tokens are associated with scopes that control what
operations are permitted.

| Scope | Permits |
|-------|---------|
| `assets:read` | List and retrieve assets |
| `assets:write` | Create, update, and delete assets |
| `search:read` | Execute search queries |
| `contracts:read` | List and retrieve contracts |
| `contracts:write` | Create and manage contracts |
| `webhooks:manage` | Create, update, and delete webhooks |
| `billing:read` | View billing and usage data |
| `semantic:read` | Execute SPARQL queries and read ontology |
| `dq:read` | View data quality results |
| `dq:write` | Trigger data quality checks |
| `compliance:read` | View compliance scan results |

Request only the scopes your integration needs. Overly broad scopes
increase the blast radius if a key is compromised.


## Multi-Tenancy

Every API key and JWT token is bound to a specific tenant. All API calls
are automatically scoped to that tenant's data. You cannot access
resources belonging to other tenants.

If your integration needs cross-tenant access (rare), contact the
Platform Admin to configure a service account with cross-tenant
privileges.


## Key Rotation

Rotate API keys periodically (recommended: every 90 days).

1. Create a new key with the same scopes.
2. Update your integration to use the new key.
3. Verify the integration works.
4. Revoke the old key via **Settings > API Keys > Revoke**.


## See Also

- [How-To: Handle Webhooks](handle-webhooks.md)
- [How-To: Integrate Semantic Layer](integrate-semantic-layer.md)
- [External Developer Reference](../reference.md)
