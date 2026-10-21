# Meshant Contracts API

The Contracts API manages data contracts -- machine-readable agreements
that define the schema, quality rules, SLAs, and ownership of a data
product. Contracts can be authored in YAML or JSON, validated, linted,
and versioned through this API.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/contracts/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /contracts/ | List all data contracts in the current tenant |
| POST | /contracts/ | Create a new data contract |
| GET | /contracts/{id}/ | Get contract details by ID |
| PUT | /contracts/{id}/ | Update a contract (creates a new version) |
| DELETE | /contracts/{id}/ | Archive a contract |
| POST | /contracts/validate/ | Validate a contract document without saving |
| POST | /contracts/lint/ | Lint a contract for style and completeness issues |
| GET | /contracts/{id}/versions/ | List all versions of a contract |
| GET | /contracts/{id}/versions/{version}/ | Get a specific version |
| POST | /contracts/{id}/publish/ | Promote a draft contract to published status |

## Request / Response Examples

### POST /contracts/

**Request body:**

```json
{
  "name": "Customer Events v2",
  "description": "Schema contract for the customer-events stream",
  "format": "yaml",
  "body": "schema:\n  type: object\n  properties:\n    event_id:\n      type: string\n    timestamp:\n      type: string\n      format: date-time\n",
  "owner_id": "usr_abc123"
}
```

**Response 201:**

```json
{
  "id": "ctr_aaa111",
  "name": "Customer Events v2",
  "version": 1,
  "status": "draft",
  "created_at": "2026-04-09T11:00:00Z"
}
```

### POST /contracts/lint/

**Response 200:**

```json
{
  "valid": true,
  "warnings": [
    {"path": "schema.properties.timestamp", "message": "Consider adding a description"}
  ],
  "errors": []
}
```

## Common Parameters

- `page` (int) -- Page number for pagination.
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `status` (string) -- Filter by status: `draft`, `published`, `archived`.
- `owner_id` (string) -- Filter by contract owner.
- `search` (string) -- Full-text search on name and description.

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 400 | `CONTRACT_INVALID` | Contract body fails schema validation |
| 404 | `CONTRACT_NOT_FOUND` | Contract ID does not exist |
| 409 | `CONTRACT_ALREADY_PUBLISHED` | Cannot edit a published contract directly |
| 422 | `CONTRACT_LINT_ERRORS` | Lint found blocking errors |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub contracts`](../cli-reference/contracts.md)
- SDK: [`ContractsAPI`](../sdk-reference/python/contracts.md)
