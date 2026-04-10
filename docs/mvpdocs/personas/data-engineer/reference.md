# Data Engineer -- Reference

Quick-reference table linking every capability area to the matching API
endpoint group, CLI command group, and Python SDK class.

## Reference Matrix

| Area | API Reference | CLI Reference | SDK Reference |
|------|--------------|---------------|---------------|
| Assets | [/api/v1/assets](../../api-reference/assets.md) | [`datahub asset`](../../cli-reference/asset.md) | [AssetsAPI](../../sdk-reference/python/assets.md) |
| Contracts | [/api/v1/contracts](../../api-reference/contracts.md) | [`datahub contract`](../../cli-reference/contract.md) | [ContractsAPI](../../sdk-reference/python/contracts.md) |
| Data Quality | [/api/v1/dq](../../api-reference/dq.md) | [`datahub dq`](../../cli-reference/dq.md) | [DQAPI](../../sdk-reference/python/dq.md) |
| Compliance | [/api/v1/compliance](../../api-reference/compliance.md) | [`datahub compliance`](../../cli-reference/compliance.md) | [ComplianceAPI](../../sdk-reference/python/compliance.md) |
| Jobs | [/api/v1/jobs](../../api-reference/jobs.md) | [`datahub jobs`](../../cli-reference/jobs.md) | [JobsAPI](../../sdk-reference/python/jobs.md) |
| Semantic | [/api/v1/semantic](../../api-reference/semantic.md) | [`datahub semantic`](../../cli-reference/semantic.md) | [SemanticAPI](../../sdk-reference/python/semantic.md) |
| Transformations | [/api/v1/transformations](../../api-reference/transformations.md) | [`datahub transformation`](../../cli-reference/transformation.md) | [TransformationsAPI](../../sdk-reference/python/transformations.md) |
| Files | [/api/v1/files](../../api-reference/files.md) | [`datahub files`](../../cli-reference/files.md) | [FilesAPI](../../sdk-reference/python/files.md) |
| Webhooks | [/api/v1/webhooks](../../api-reference/webhooks.md) | [`datahub webhooks`](../../cli-reference/webhooks.md) | [WebhooksAPI](../../sdk-reference/python/webhooks.md) |

## Common Patterns

**Validate a contract in CI:**

```bash
datahub contract validate contracts/*.yaml --strict
```

**Poll a job until completion:**

```python
from datahub_sdk import MeshantClient
import time

client = MeshantClient()
run = client.dq.run(asset_id="<ASSET_ID>")

while run.status in ("pending", "running"):
    time.sleep(5)
    run = client.jobs.get(run.id)

print(f"Final status: {run.status}")
```

## See Also

- [Error Codes](../../reference/error-codes.md)
- [Authentication Guide](../../reference/authentication.md)
- [Pagination](../../reference/pagination.md)
