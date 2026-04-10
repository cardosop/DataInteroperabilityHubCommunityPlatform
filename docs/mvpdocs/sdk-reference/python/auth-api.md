# AuthAPI

`from datahub_interoperability import AuthAPI`

Handles authentication flows including login, logout, token refresh, email
verification, and password reset. AuthAPI manages JWT bearer tokens and
supports both interactive and programmatic authentication.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.auth  # type: AuthAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `login(email, password)` | Authenticate and obtain tokens | `TokenPair` |
| `logout()` | Invalidate the current session | `None` |
| `refresh(refresh_token)` | Refresh an expired access token | `TokenPair` |
| `verify_email(token)` | Verify a user email address | `None` |
| `request_password_reset(email)` | Send a password reset email | `None` |
| `reset_password(token, new_password)` | Complete password reset | `None` |
| `me()` | Get current authenticated user info | `User` |

## Example

```python
tokens = api.login(email="user@example.com", password="s3cret")
print(tokens.access_token)
api.refresh(tokens.refresh_token)
```

## Error Handling

```python
from datahub_interoperability import AuthAPI, MVPGatedFeatureError

try:
    result = api.login(email="user@example.com", password="pass")
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/auth/`](../../api-reference/auth.md)
- CLI: [`datahub auth`](../../cli-reference/auth.md)
