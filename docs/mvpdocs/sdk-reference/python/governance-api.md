# GovernanceAPI

`from datahub_interoperability import GovernanceAPI`

Manages governance policies, retention rules, and classification labels.
GovernanceAPI enables platform administrators to define and enforce data
governance rules across all assets in the tenant.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.governance  # type: GovernanceAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list_policies(page=1, page_size=20)` | List governance policies | `list[Policy]` |
| `get_policy(id)` | Get policy by UUID | `Policy` |
| `create_policy(name, rules)` | Create a governance policy | `Policy` |
| `update_policy(id, **kwargs)` | Update a policy | `Policy` |
| `delete_policy(id)` | Delete a policy | `None` |
| `list_retention_rules()` | List data retention rules | `list[RetentionRule]` |
| `set_retention_rule(asset_id, days)` | Set retention period for an asset | `RetentionRule` |

## Example

```python
policy = api.create_policy(
    name="pii_handling",
    rules={"classification": "pii", "action": "encrypt"}
)
api.set_retention_rule(asset_id="a-100", days=365)
```

## Error Handling

```python
from datahub_interoperability import GovernanceAPI, MVPGatedFeatureError

try:
    result = api.list_policies()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/governance/`](../../api-reference/governance.md)
- CLI: [`datahub governance`](../../cli-reference/governance.md)
