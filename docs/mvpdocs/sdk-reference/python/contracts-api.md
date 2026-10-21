# ContractsAPI

`from datahub_interoperability import ContractsAPI`

Manages data contracts that define the schema, quality expectations, and
SLAs for data assets. ContractsAPI supports authoring, validation, linting,
and versioning of contracts in YAML or JSON format.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.contracts  # type: ContractsAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list(page=1, page_size=20, status=None)` | List all contracts | `list[Contract]` |
| `get(id)` | Get contract by UUID | `Contract` |
| `create(name, schema, sla=None)` | Create a new contract | `Contract` |
| `update(id, **kwargs)` | Update contract fields | `Contract` |
| `validate(id)` | Validate contract against its schema | `ValidationResult` |
| `lint(id)` | Lint contract for best-practice issues | `list[LintIssue]` |
| `delete(id)` | Delete a draft contract | `None` |

## Example

```python
contract = api.create(name="orders_v2", schema={"type": "object"})
result = api.validate(contract.id)
print(result.is_valid)
```

## Error Handling

```python
from datahub_interoperability import ContractsAPI, MVPGatedFeatureError

try:
    result = api.list()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/contracts/`](../../api-reference/contracts.md)
- CLI: [`datahub contracts`](../../cli-reference/contracts.md)
