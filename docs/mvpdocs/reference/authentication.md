# Authentication

Meshant supports multiple authentication methods. All API requests (except
public endpoints like login and email verification) require valid credentials.

## Authentication Methods

### JWT Bearer Tokens

The primary authentication method. Obtain a token pair by logging in:

```bash
curl -X POST https://meshant-internal.example.com/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "s3cret"}'
```

Response:

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 900
}
```

Include the access token in subsequent requests:

```bash
curl -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \
  https://meshant-internal.example.com/api/v1/assets/
```

SDK equivalent:

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="msh_live_...")
# or authenticate with email/password:
client = DataHubClient(base_url="https://meshant-internal.example.com")
client.auth.login(email="user@example.com", password="s3cret")
```

### Token Lifetime

| Token | Lifetime | Notes |
|-------|----------|-------|
| Access token | 15 minutes | Short-lived; include in every request |
| Refresh token | 7 days | Used to obtain new access tokens |

### Refresh Flow

When the access token expires, use the refresh token to obtain a new pair:

```bash
curl -X POST https://meshant-internal.example.com/api/v1/auth/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "eyJhbGciOiJSUzI1NiIs..."}'
```

The response contains a new `access_token` and `refresh_token`. The old
refresh token is invalidated (rotation).

### API Key Authentication

For server-to-server integrations, use long-lived API keys:

```bash
curl -H "Authorization: ApiKey msh_live_abc123..." \
  https://meshant-internal.example.com/api/v1/assets/
```

API keys are scoped to a specific tenant and set of permissions. Generate
them from the Developer portal or via the API:

```bash
curl -X POST https://meshant-internal.example.com/api/v1/developer/api-keys/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "CI Pipeline", "scopes": ["assets:read", "dq:write"]}'
```

### SSO (SAML / OIDC)

Enterprise tenants can configure SAML 2.0 or OpenID Connect for single
sign-on. SSO configuration is managed in tenant settings:

- **SAML 2.0** -- provide the IdP metadata URL or XML.
- **OIDC** -- provide the issuer URL, client ID, and client secret.

After SSO is configured, users authenticate through the IdP and receive
Meshant JWT tokens via the callback flow.

## Scopes and Permissions

API keys and tokens carry scopes that restrict access:

| Scope | Description |
|-------|-------------|
| `assets:read` | Read asset metadata and data |
| `assets:write` | Create, update, publish, retire assets |
| `contracts:read` | Read contracts |
| `contracts:write` | Create and update contracts |
| `dq:read` | Read DQ results |
| `dq:write` | Trigger DQ checks |
| `compliance:read` | Read compliance findings |
| `compliance:write` | Trigger compliance scans |
| `admin` | Full administrative access |

Scopes follow the pattern `{resource}:{action}`. A token with no explicit
scopes has the permissions of the authenticated user's role.

## Multi-Tenant Context

Every request is scoped to a tenant. The tenant is determined by:

1. The `X-Tenant-ID` header (if provided).
2. The default tenant of the authenticated user.
3. The tenant bound to the API key.

```bash
curl -H "Authorization: Bearer $TOKEN" \
  -H "X-Tenant-ID: tenant-uuid-here" \
  https://meshant-internal.example.com/api/v1/assets/
```

## Related

- [Error Codes](error-codes.md) -- 401 and 403 error handling
- [Rate Limits](rate-limits.md) -- per-key rate limits
- [SDK AuthAPI](../sdk-reference/python/auth-api.md) -- Python SDK authentication
