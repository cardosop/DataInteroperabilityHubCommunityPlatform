# Meshant Data Quality API

The Data Quality (DQ) API runs automated quality checks against datasets
and assets. It supports configurable quality profiles with rules for
completeness, uniqueness, range validation, and custom expressions.
Results are stored historically so teams can track quality trends.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/dq/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /dq/profiles/ | List data quality profiles |
| POST | /dq/profiles/ | Create a new quality profile |
| GET | /dq/profiles/{id}/ | Get profile details by ID |
| PUT | /dq/profiles/{id}/ | Update a quality profile |
| DELETE | /dq/profiles/{id}/ | Delete a quality profile |
| POST | /dq/check/ | Run a quality check against a dataset |
| GET | /dq/results/ | List quality check results |
| GET | /dq/results/{id}/ | Get detailed results for a specific check run |
| GET | /dq/results/{id}/failures/ | List individual row-level failures |
| GET | /dq/trends/{dataset_id}/ | Quality score trend over time for a dataset |

## Request / Response Examples

### POST /dq/check/

**Request body:**

```json
{
  "dataset_id": "ds_abc123",
  "profile_id": "dqp_001",
  "sample_pct": 100
}
```

**Response 202:**

```json
{
  "job_id": "job_dq_456",
  "status": "queued"
}
```

### GET /dq/results/{id}/

**Response 200:**

```json
{
  "id": "dqr_789",
  "dataset_id": "ds_abc123",
  "profile_id": "dqp_001",
  "score": 94.5,
  "rules_passed": 17,
  "rules_failed": 1,
  "rules_total": 18,
  "completed_at": "2026-04-09T12:15:00Z",
  "failures_summary": [
    {"rule": "amount_not_null", "failure_count": 23, "severity": "error"}
  ]
}
```

## Common Parameters

- `page` (int) -- Page number for pagination.
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `dataset_id` (string) -- Filter results by dataset.
- `profile_id` (string) -- Filter results by quality profile.
- `min_score` (float) -- Only results with score >= this value.
- `since` (datetime) -- Only results after this timestamp (ISO 8601).

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 404 | `DQ_PROFILE_NOT_FOUND` | Quality profile ID does not exist |
| 404 | `DQ_RESULT_NOT_FOUND` | Result ID does not exist |
| 422 | `DQ_PROFILE_INVALID` | Profile contains invalid rule definitions |
| 422 | `DQ_DATASET_INCOMPATIBLE` | Dataset format not supported by the profile |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub dq`](../cli-reference/dq.md)
- SDK: [`DataQualityAPI`](../sdk-reference/python/dq.md)
