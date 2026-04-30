# Error Codes

Every error response from the Meshant API returns a consistent JSON envelope
with an HTTP status code, a machine-readable error code, a human-readable
message, and optional structured details.

## Error Response Format

```json
{
  "error": {
    "code": "ASSET_NOT_FOUND",
    "message": "Asset with ID a-999 does not exist.",
    "http_status": 404,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-04-17T12:00:00Z",
    "details": {
      "asset_id": "a-999"
    }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `error.code` | `string` | Machine-readable error code (see tables below) |
| `error.message` | `string` | Human-readable description |
| `error.http_status` | `integer` | HTTP status code |
| `error.request_id` | `string` | UUID for support tickets |
| `error.timestamp` | `string` | ISO 8601 UTC timestamp |
| `error.details` | `object` | Optional context-specific fields |

## Standard HTTP Error Codes

| Status | Meaning | When It Occurs |
|--------|---------|----------------|
| `400` | Bad Request | Malformed JSON, missing required fields, invalid query parameters |
| `401` | Unauthorized | Missing or expired JWT token, invalid API key |
| `403` | Forbidden | Authenticated but insufficient permissions for the requested action |
| `404` | Not Found | Resource does not exist or is not accessible in the current tenant |
| `409` | Conflict | Resource already exists, version conflict, or state transition violation |
| `422` | Unprocessable Entity | Request is well-formed but fails business validation rules |
| `429` | Too Many Requests | Rate limit exceeded; check `Retry-After` header |
| `500` | Internal Server Error | Unexpected server failure; retry with exponential backoff |

## Domain-Specific Error Codes

These codes appear in the `code` field of the error response body alongside
the appropriate HTTP status code.

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `ASSET_NOT_FOUND` | 404 | The requested asset does not exist in the current tenant |
| `CONTRACT_VALIDATION_FAILED` | 422 | The data contract failed schema or rule validation |
| `DQ_CHECK_FAILED` | 422 | One or more data quality checks did not pass |
| `COMPLIANCE_SCAN_FAILED` | 422 | The compliance scan encountered errors during execution |
| `MVP_FEATURE_GATED` | 403 | The requested feature is not available in the current MVP release |
| `QUOTA_EXCEEDED` | 429 | The tenant has exceeded its usage quota for this resource |
| `TENANT_NOT_FOUND` | 404 | The specified tenant does not exist or the user has no access |
| `WEBHOOK_DELIVERY_FAILED` | 422 | The webhook endpoint did not respond with a 2xx status |
| `AUTH_TOKEN_EXPIRED` | 401 | The JWT access token has expired; use the refresh endpoint |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests; see `X-RateLimit-Reset` header for retry time |

## Structureless-Contract Codes (Phase 227)

These codes ship with Phase 227's structural-floor enforcement. The
floor is **always-on** — no feature flag, no per-tenant override.

| Code | HTTP Status | Description |
| ---- | ----------- | ----------- |
| `STRUCTURELESS_CONTRACT` | 400 (create/update), 422 (publish gate) | The submitted/active contract has no resolvable models or schema fields. `details.subcode` carries the per-cause taxonomy below. |
| `VALIDATION_ERROR` | 400 | Pydantic-level rejection (missing `info.name`, malformed JSON, etc.) on contract create/update — distinct from `STRUCTURELESS_CONTRACT`. |
| `NORMALIZATION_FAILED` | 400 | The engine could not normalise the document (parse failure, malformed YAML, etc.). |
| `SCHEMA_TOO_DEEP` | 400 | ODCS recursive-properties walker hit `CONTRACTS_MAX_NESTING_DEPTH` (default 20). `details.max_depth` and `details.path` identify the offending field. |
| `INVALID_YAML` | 400 | YAML body contains an unsafe construct (e.g., `!!python/object/apply:os.system`). |
| `PRECONDITION_FAILED` | 412 | `If-Match` ETag mismatch on PATCH `/contracts/{id}/`. The response body and `ETag` header carry the server's current value. |
| `PAYLOAD_TOO_LARGE` | 413 | Contract body's `original_raw` exceeds the 2 MB cap. `details.limit_bytes` and `details.size_bytes` identify the gap. |

### `STRUCTURELESS_CONTRACT` — `details.subcode` taxonomy

`STRUCTURELESS_CONTRACT` errors carry a per-cause subcode in
`error.details.subcode` so clients can branch programmatically.
Every payload also includes `models_count`,
`schema_fields_count`, `spec_type`, `spec_version`, a per-cause
`hint`, and a `remediation_url` deep-linking to the Schema editor
for the offending contract.

| `details.subcode` | Cause | Recommended remediation |
| ----------------- | ----- | ----------------------- |
| `STRUCTURELESS_ODPS_NO_PORTS` | ODPS contract has no resolvable `outputPorts[*]` schemas. | Add at least one outputPort with a `contract.spec.schema.fields[]`, `dataSchema.fields[]`, or a `contractId` referencing an existing ODCS contract. |
| `STRUCTURELESS_ODCS_NO_SCHEMA` | ODCS contract has no `schema.fields[]` and no `models[*].fields[]`. | Open the Schema editor and add at least one model with one field. |
| `STRUCTURELESS_CYCLIC_PORTS` | ODPS port resolution detected a cycle (A → B → A). | Fix the circular `contractId` reference, then retry. |
| `STRUCTURELESS_GENERIC` | Non-ODPS/ODCS spec_type or unrecognised shape. | Operator investigation; ping #data-governance Slack. |

### Example error response

```json
{
  "error": {
    "code": "STRUCTURELESS_CONTRACT",
    "message": "Contract failed the structural-floor invariant: it has no resolvable models or schema fields after normalisation. (STRUCTURELESS_ODPS_NO_PORTS)",
    "http_status": 400,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-04-30T12:00:00Z",
    "details": {
      "subcode": "STRUCTURELESS_ODPS_NO_PORTS",
      "models_count": 0,
      "schema_fields_count": 0,
      "spec_type": "ODPS",
      "spec_version": "bitol-1.0.0",
      "hint": "ODPS contract has no resolvable outputPort schemas. Add at least one outputPort with a `contract.spec.schema.fields[]`, `dataSchema.fields[]`, or a `contractId` referencing an existing ODCS contract.",
      "remediation_url": "https://stagingmeshant-internal.example.com/contracts/550e8400-e29b-41d4-a716-446655440000/edit?tab=schema"
    }
  }
}
```

See [`docs/CONTRACTS.md`](../../CONTRACTS.md) for the canonical
contract shapes per spec version that pass the floor, and the
[ops runbook](../../runbooks/structureless-contracts.md) for tenant
rejection triage.

## SDK Exception Mapping

The Python SDK maps these codes to typed exceptions:

```python
from datahub_interoperability import (
    DataHubClient,
    NotFoundError,          # 404
    ValidationError,        # 422
    AuthenticationError,    # 401
    ForbiddenError,         # 403
    ConflictError,          # 409
    RateLimitError,         # 429
    MVPGatedFeatureError,   # MVP_FEATURE_GATED
    ServerError,            # 500
)

client = DataHubClient(api_key="msh_live_...")
try:
    asset = client.assets.get("a-999")
except NotFoundError as e:
    print(f"Code: {e.code}, Message: {e.message}")
except RateLimitError as e:
    print(f"Retry after {e.retry_after} seconds")
```

## Handling Errors in curl

```bash
curl -s -w "\nHTTP_STATUS:%{http_code}\n" \
  -H "Authorization: Bearer $TOKEN" \
  https://meshant-internal.example.com/api/v1/assets/a-999/
```

A non-2xx response always includes the JSON error body described above.

## Best Practices

- Always check the `code` field for programmatic error handling, not the
  `message` field which may change between releases.
- Log the `request_id` value when reporting issues to Meshant support.
- On `429` responses, respect the `Retry-After` header before retrying.
- On `500` responses, retry with exponential backoff (initial delay 1s,
  max 3 retries).

## Related

- [Authentication](authentication.md) -- token lifecycle and 401 handling
- [Rate Limits](rate-limits.md) -- rate limit headers and backoff strategies
- [Conventions](conventions.md) -- general API conventions
