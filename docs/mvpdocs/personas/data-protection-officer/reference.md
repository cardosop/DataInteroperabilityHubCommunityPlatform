# Data Product Owner -- Reference

Quick-reference table linking every capability area to the matching API
endpoint group, CLI command group, and Python SDK class. Use these links
when you need the full parameter details for a specific operation.

## Reference Matrix

| Area | API Reference | CLI Reference | SDK Reference |
|------|--------------|---------------|---------------|
| Assets | [/api/v1/assets](../../api-reference/assets.md) | [`datahub asset`](../../cli-reference/asset.md) | [AssetsAPI](../../sdk-reference/python/assets.md) |
| Contracts | [/api/v1/contracts](../../api-reference/contracts.md) | [`datahub contract`](../../cli-reference/contract.md) | [ContractsAPI](../../sdk-reference/python/contracts.md) |
| Data Quality | [/api/v1/dq](../../api-reference/dq.md) | [`datahub dq`](../../cli-reference/dq.md) | [DQAPI](../../sdk-reference/python/dq.md) |
| Compliance | [/api/v1/compliance](../../api-reference/compliance.md) | [`datahub compliance`](../../cli-reference/compliance.md) | [ComplianceAPI](../../sdk-reference/python/compliance.md) |
| Marketplace | [/api/v1/marketplace](../../api-reference/marketplace.md) | [`datahub marketplace`](../../cli-reference/marketplace.md) | [MarketplaceAPI](../../sdk-reference/python/marketplace.md) |
| Jobs | [/api/v1/jobs](../../api-reference/jobs.md) | [`datahub jobs`](../../cli-reference/jobs.md) | [JobsAPI](../../sdk-reference/python/jobs.md) |
| Files | [/api/v1/files](../../api-reference/files.md) | [`datahub files`](../../cli-reference/files.md) | [FilesAPI](../../sdk-reference/python/files.md) |

## Common Patterns

**List your assets with pagination:**

```
GET /api/v1/assets?domain=finance&page=1&page_size=25
```

```bash
datahub asset list --domain finance --page 1 --page-size 25
```

```python
from datahub_interoperability import DataHubClient
client = DataHubClient()
assets = client.assets.list(domain="finance", page=1, page_size=25)
```

## See Also

- [Error Codes](../../reference/error-codes.md)
- [Authentication Guide](../../reference/authentication.md)
- [Pagination](../../reference/pagination.md)
