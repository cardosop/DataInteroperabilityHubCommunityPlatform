# TenantsAPI

`from datahub_interoperability import TenantsAPI`

Manages multi-tenancy including tenant creation, member invitations, and
context switching. Every resource in Meshant belongs to a tenant, and
TenantsAPI provides administrative operations for tenant lifecycle.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.tenants  # type: TenantsAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list(page=1, page_size=20)` | List tenants the user belongs to | `list[Tenant]` |
| `get(id)` | Get tenant by UUID | `Tenant` |
| `create(name, slug)` | Create a new tenant | `Tenant` |
| `update(id, **kwargs)` | Update tenant settings | `Tenant` |
| `invite_member(tenant_id, email, role)` | Invite a user to the tenant | `Invitation` |
| `list_members(tenant_id, page=1, page_size=20)` | List tenant members | `list[Member]` |
| `remove_member(tenant_id, user_id)` | Remove a member from the tenant | `None` |

## Example

```python
tenant = api.create(name="Acme Corp", slug="acme")
api.invite_member(tenant.id, email="alice@acme.com", role="editor")
```

## Error Handling

```python
from datahub_interoperability import TenantsAPI, MVPGatedFeatureError

try:
    result = api.list()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/tenants/`](../../api-reference/tenants.md)
- CLI: [`datahub tenants`](../../cli-reference/tenants.md)
