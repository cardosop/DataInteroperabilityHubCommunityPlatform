# Meshant Compliance API

The Compliance API automates regulatory scanning of datasets and assets.
It detects personally identifiable information (PII), evaluates data
against configurable compliance policies, and produces findings that
can be reviewed, acknowledged, or remediated by data stewards.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/compliance/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /compliance/scans/ | List compliance scan runs |
| POST | /compliance/scans/ | Start a new compliance scan |
| GET | /compliance/scans/{id}/ | Get scan details and summary |
| GET | /compliance/scans/{id}/findings/ | List individual findings from a scan |
| PUT | /compliance/findings/{id}/ | Update finding status (acknowledge, resolve, etc.) |
| GET | /compliance/policies/ | List compliance policies |
| POST | /compliance/policies/ | Create a custom compliance policy |
| GET | /compliance/policies/{id}/ | Get policy details |
| PUT | /compliance/policies/{id}/ | Update a compliance policy |
| DELETE | /compliance/policies/{id}/ | Delete a compliance policy |

## Request / Response Examples

### POST /compliance/scans/

**Request body:**

```json
{
  "dataset_id": "ds_abc123",
  "policy_ids": ["pol_gdpr", "pol_hipaa"],
  "sample_rows": 10000
}
```

**Response 202:**

```json
{
  "job_id": "job_comp_789",
  "scan_id": "scan_001",
  "status": "queued"
}
```

### GET /compliance/scans/{id}/findings/

**Response 200:**

```json
{
  "count": 3,
  "results": [
    {
      "id": "fnd_001",
      "column": "customer_email",
      "pii_type": "email_address",
      "confidence": 0.98,
      "policy_id": "pol_gdpr",
      "severity": "high",
      "status": "open",
      "detected_at": "2026-04-09T13:00:00Z"
    }
  ]
}
```

## Common Parameters

- `page` (int) -- Page number for pagination.
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `dataset_id` (string) -- Filter scans by dataset.
- `policy_id` (string) -- Filter by compliance policy.
- `severity` (string) -- Filter findings by severity: `low`, `medium`, `high`, `critical`.
- `status` (string) -- Filter findings by status: `open`, `acknowledged`, `resolved`.

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 404 | `COMPLIANCE_SCAN_NOT_FOUND` | Scan ID does not exist |
| 404 | `COMPLIANCE_FINDING_NOT_FOUND` | Finding ID does not exist |
| 404 | `COMPLIANCE_POLICY_NOT_FOUND` | Policy ID does not exist |
| 422 | `COMPLIANCE_POLICY_INVALID` | Policy definition contains invalid rules |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub compliance`](../cli-reference/compliance.md)
- SDK: [`ComplianceAPI`](../sdk-reference/python/compliance.md)
