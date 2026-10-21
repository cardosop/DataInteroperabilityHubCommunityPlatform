# Meshant Datasets API

The Datasets API manages tabular and semi-structured datasets on the
Meshant platform. It supports schema inference from uploaded files,
manual schema definition, validation against data contracts, and full
CRUD lifecycle operations.

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/datasets/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /datasets/ | List datasets in the current tenant |
| POST | /datasets/ | Create a new dataset |
| GET | /datasets/{id}/ | Get dataset details by ID |
| PUT | /datasets/{id}/ | Update dataset metadata or schema |
| DELETE | /datasets/{id}/ | Delete a dataset |
| POST | /datasets/{id}/infer-schema/ | Infer schema from the dataset's source file |
| GET | /datasets/{id}/schema/ | Get the current schema for a dataset |
| POST | /datasets/{id}/validate/ | Validate dataset contents against its schema |
| GET | /datasets/{id}/preview/ | Return the first N rows as JSON |
| GET | /datasets/{id}/stats/ | Column-level statistics (min, max, null count, etc.) |

## Request / Response Examples

### POST /datasets/

**Request body:**

```json
{
  "name": "Q1 Sales",
  "description": "Quarterly sales data for 2026-Q1",
  "file_id": "file_aaa111",
  "format": "csv",
  "tags": ["sales", "quarterly"]
}
```

**Response 201:**

```json
{
  "id": "ds_abc123",
  "name": "Q1 Sales",
  "format": "csv",
  "row_count": null,
  "schema_status": "pending",
  "created_at": "2026-04-09T10:30:00Z"
}
```

### POST /datasets/{id}/infer-schema/

**Response 200:**

```json
{
  "columns": [
    {"name": "id", "type": "integer", "nullable": false},
    {"name": "amount", "type": "decimal", "nullable": false},
    {"name": "date", "type": "date", "nullable": true}
  ],
  "inferred_at": "2026-04-09T10:31:00Z"
}
```

## Common Parameters

- `page` (int) -- Page number for pagination.
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `format` (string) -- Filter by file format (`csv`, `parquet`, `json`).
- `tags` (string) -- Comma-separated tag filter.
- `search` (string) -- Full-text search on name and description.

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 400 | `DATASET_SCHEMA_INVALID` | Manually provided schema is malformed |
| 404 | `DATASET_NOT_FOUND` | Dataset ID does not exist |
| 409 | `DATASET_NAME_CONFLICT` | A dataset with this name already exists |
| 422 | `DATASET_VALIDATION_FAILED` | Contents do not match the schema |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub datasets`](../cli-reference/datasets.md)
- SDK: [`DatasetsAPI`](../sdk-reference/python/datasets.md)
