# UsersAPI

`from datahub_interoperability import UsersAPI`

Manages user accounts, role assignments, and permissions within a tenant.
UsersAPI provides CRUD operations for user profiles and the ability to
assign roles that control access to platform features.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.users  # type: UsersAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list(page=1, page_size=20, role=None)` | List users in the current tenant | `list[User]` |
| `get(id)` | Get user by UUID | `User` |
| `create(email, first_name, last_name, role="viewer")` | Create a user account | `User` |
| `update(id, **kwargs)` | Update user profile | `User` |
| `assign_role(user_id, role)` | Assign a role to a user | `User` |
| `deactivate(id)` | Deactivate a user account | `User` |
| `delete(id)` | Permanently delete a user | `None` |

## Example

```python
users = api.list(role="admin")
api.assign_role(users[0].id, role="editor")
```

## Error Handling

```python
from datahub_interoperability import UsersAPI, MVPGatedFeatureError

try:
    result = api.list()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/users/`](../../api-reference/users.md)
- CLI: [`datahub users`](../../cli-reference/users.md)
