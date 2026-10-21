# ComplianceAPI

`from datahub_interoperability import ComplianceAPI`

Runs compliance scans against data assets to detect PII, sensitive data,
and policy violations. ComplianceAPI supports automated scanning, finding
review, and remediation tracking across all governed assets.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.compliance  # type: ComplianceAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list_scans(page=1, page_size=20, asset_id=None)` | List compliance scan runs | `list[ComplianceScan]` |
| `get_scan(id)` | Get scan details by ID | `ComplianceScan` |
| `trigger_scan(asset_id, policy_ids=None)` | Trigger a new compliance scan | `ComplianceScan` |
| `list_findings(scan_id, severity=None)` | List findings for a scan | `list[Finding]` |
| `review_finding(finding_id, status, comment=None)` | Review and update a finding | `Finding` |

## Example

```python
scan = api.trigger_scan(asset_id="a-456", policy_ids=["pol-1"])
findings = api.list_findings(scan.id, severity="high")
```

## Error Handling

```python
from datahub_interoperability import ComplianceAPI, MVPGatedFeatureError

try:
    result = api.list_scans()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/compliance/`](../../api-reference/compliance.md)
- CLI: [`datahub compliance`](../../cli-reference/compliance.md)
