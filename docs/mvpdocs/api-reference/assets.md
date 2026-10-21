# Meshant Assets API

The Assets API manages data assets -- the central catalog entities that
tie together datasets, contracts, quality profiles, and compliance
metadata. Assets can be created via a data-first flow (upload then
attach a contract) or a contract-first flow (define the contract then
populate data).

## Authentication

All endpoints require a valid JWT bearer token or API key in the
`Authorization` header. See [Authentication](../reference/authentication.md).

## Base Path

`/api/v1/assets/`

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /assets/ | List data assets in the current tenant |
| POST | /assets/ | Create a new data asset |
| GET | /assets/{id}/ | Get asset details by ID |
| PUT | /assets/{id}/ | Update asset metadata |
| DELETE | /assets/{id}/ | Archive a data asset |
| POST | /assets/{id}/attach-contract/ | Bind a data contract to this asset |
| POST | /assets/{id}/attach-dataset/ | Bind a dataset to this asset |
| GET | /assets/{id}/lineage/ | Get upstream and downstream lineage |
| GET | /assets/{id}/quality/ | Get the latest data quality summary |
| POST | /assets/{id}/publish/ | Publish the asset to the marketplace |

## Request / Response Examples

### POST /assets/ (data-first)

**Request body:**

```json
{
  "name": "Q1 Sales Asset",
  "description": "Curated quarterly sales data",
  "dataset_id": "ds_abc123",
  "tags": ["sales", "curated"],
  "domain": "finance"
}
```

**Response 201:**

```json
{
  "id": "ast_001",
  "name": "Q1 Sales Asset",
  "status": "draft",
  "dataset_id": "ds_abc123",
  "contract_id": null,
  "domain": "finance",
  "created_at": "2026-04-09T12:00:00Z"
}
```

### POST /assets/ (contract-first)

**Request body:**

```json
{
  "name": "Customer Events Asset",
  "contract_id": "ctr_aaa111",
  "domain": "marketing"
}
```

## Common Parameters

- `page` (int) -- Page number for pagination.
- `page_size` (int) -- Items per page (default: 20, max: 100).
- `status` (string) -- Filter by status: `draft`, `published`, `archived`.
- `domain` (string) -- Filter by business domain.
- `tags` (string) -- Comma-separated tag filter.
- `search` (string) -- Full-text search on name and description.

## Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 400 | `ASSET_MISSING_SOURCE` | Either dataset_id or contract_id is required |
| 404 | `ASSET_NOT_FOUND` | Asset ID does not exist |
| 409 | `ASSET_ALREADY_PUBLISHED` | Cannot archive a published asset without unpublishing |
| 422 | `ASSET_CONTRACT_MISMATCH` | Dataset schema does not match the attached contract |

See [Error Codes](../reference/error-codes.md) for the full list.

## Related

- CLI: [`datahub assets`](../cli-reference/assets.md)
- SDK: [`AssetsAPI`](../sdk-reference/python/assets.md)
