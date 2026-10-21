# Meshant Governance API

The Governance API enforces data governance policies across the Meshant
platform. It manages retention schedules, data classification labels,
consent records, and GDPR data-subject rights requests such as access,
rectification, and erasure.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/governance/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /governance/policies/ | List governance policies |
| POST | /governance/policies/ | Create a governance policy |
| GET | /governance/policies/{id}/ | Get policy details |
| PUT | /governance/policies/{id}/ | Update a governance policy |
| DELETE | /governance/policies/{id}/ | Delete a governance policy |
| GET | /governance/retention/ | List retention rules |
| POST | /governance/retention/ | Create a retention rule for a dataset or domain |
| PUT | /governance/retention/{id}/ | Update a retention rule |
| DELETE | /governance/retention/{id}/ | Delete a retention rule |
| GET | /governance/consent/ | List consent records |
| POST | /governance/consent/ | Record consent for a data subject |
| GET | /governance/dsar/ | List data-subject access requests (DSAR) |
| POST | /governance/dsar/ | Submit a new DSAR |
| GET | /governance/dsar/{id}/ | Get DSAR status and results |
| PUT | /governance/dsar/{id}/ | Update DSAR status (fulfill, reject) |

## Request / Response Examples

### POST /governance/policies/

**Request body:**

```json
{
  "name": "PII Encryption Required",
  "description": "All columns classified as PII must be encrypted at rest",
  "scope": "tenant",
  "enforcement": "blocking",
  "rules": [
    {"classification": "pii", "requirement": "encryption_at_rest"}
  ]
}
```

**Response 201:**

```json
{
  "id": "gov_001",
  "name": "PII Encryption Required",
  "enforcement": "blocking",
  "status": "active",
  "created_at": "2026-04-09T17:00:00Z"
}
```

### POST /governance/dsar/

**Request body:**

```json
{
  "subject_email": "user@example.com",
  "request_type": "erasure",
  "justification": "GDPR Article 17 right to erasure"
}
```

**Response 201:**

```json
{
  "id": "dsar_001",
  "request_type": "erasure",
  "status": "pending",
  "deadline": "2026-05-09T17:00:00Z"
}
```

## Common Parameters

- `page` (int) -- Page number for pagination.
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `enforcement` (string) -- Filter policies: `blocking`, `warning`, `audit_only`.
- `request_type` (string) -- Filter DSARs: `access`, `rectification`, `erasure`, `portability`.
- `status` (string) -- Filter by status: `active`, `pending`, `fulfilled`, `rejected`.

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 404 | `GOVERNANCE_POLICY_NOT_FOUND` | Policy ID does not exist |
| 404 | `GOVERNANCE_DSAR_NOT_FOUND` | DSAR ID does not exist |
| 409 | `GOVERNANCE_RETENTION_CONFLICT` | A retention rule already exists for this scope |
| 422 | `GOVERNANCE_POLICY_INVALID` | Policy definition contains invalid rules |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub governance`](../cli-reference/governance.md)
- SDK: [`GovernanceAPI`](../sdk-reference/python/governance.md)
