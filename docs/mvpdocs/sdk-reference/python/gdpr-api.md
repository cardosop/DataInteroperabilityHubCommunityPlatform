# GDPRAPI

`from datahub_interoperability import GDPRAPI`

Manages GDPR data subject rights including access requests, erasure
(right to be forgotten), portability exports, and consent management.
GDPRAPI provides programmatic access to privacy operations required
for regulatory compliance.

## Constructor

```python
from datahub_interoperability import DataHubClient

client = DataHubClient(api_key="...", base_url="https://meshant-internal.example.com")
api = client.gdpr  # type: GDPRAPI
```

## Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `list_requests(page=1, page_size=20, type=None)` | List GDPR requests | `list[GDPRRequest]` |
| `get_request(id)` | Get GDPR request by ID | `GDPRRequest` |
| `create_access_request(subject_id)` | Create a data access request | `GDPRRequest` |
| `create_erasure_request(subject_id)` | Create a right-to-erasure request | `GDPRRequest` |
| `create_portability_request(subject_id)` | Create a data portability export | `GDPRRequest` |
| `get_consent(subject_id)` | Get consent status for a subject | `Consent` |
| `update_consent(subject_id, purposes)` | Update consent preferences | `Consent` |

## Example

```python
req = api.create_access_request(subject_id="subj-001")
print(f"Request status: {req.status}")
```

## Error Handling

```python
from datahub_interoperability import GDPRAPI, MVPGatedFeatureError

try:
    result = api.list_requests()
except MVPGatedFeatureError as e:
    print(f"Feature {e.feature} is post-MVP")
```

## Related

- API: [`/api/v1/governance/`](../../api-reference/governance.md)
- CLI: [`datahub gdpr`](../../cli-reference/gdpr.md)
