# Compliance & Privacy Officer -- Reference

Quick-reference table linking every compliance capability area to the
matching API endpoint group, CLI command group, and Python SDK class.

## Reference Matrix

| Area | API Reference | CLI Reference | SDK Reference |
|------|--------------|---------------|---------------|
| Compliance | [/api/v1/compliance](../../api-reference/compliance.md) | [`datahub compliance`](../../cli-reference/compliance.md) | [ComplianceAPI](../../sdk-reference/python/compliance.md) |
| Audit | [/api/v1/audit](../../api-reference/audit.md) | [`datahub audit`](../../cli-reference/audit.md) | [AuditAPI](../../sdk-reference/python/audit.md) |
| Governance | [/api/v1/governance](../../api-reference/governance.md) | [`datahub governance`](../../cli-reference/governance.md) | [GovernanceAPI](../../sdk-reference/python/governance.md) |
| GDPR | [/api/v1/gdpr](../../api-reference/gdpr.md) | [`datahub gdpr`](../../cli-reference/gdpr.md) | [GDPRAPI](../../sdk-reference/python/gdpr.md) |
| Assets (read) | [/api/v1/assets](../../api-reference/assets.md) | [`datahub asset`](../../cli-reference/asset.md) | [AssetsAPI](../../sdk-reference/python/assets.md) |

## Common Patterns

**Run a compliance scan and wait for results:**

```bash
datahub compliance run --asset-id <ASSET_ID> --wait
```

**Export last 30 days of audit events as JSON:**

```bash
datahub audit export --from 2026-03-10 --to 2026-04-09 --format json --output audit.json
```

**List all high-risk assets:**

```python
from datahub_sdk import MeshantClient

client = MeshantClient()
assets = client.compliance.list_assets(risk_level="high")
for a in assets:
    print(f"{a.name} — {a.risk_level}")
```

## See Also

- [Error Codes](../../reference/error-codes.md)
- [Authentication Guide](../../reference/authentication.md)
- [Compliance Concepts](../../compliance/)
