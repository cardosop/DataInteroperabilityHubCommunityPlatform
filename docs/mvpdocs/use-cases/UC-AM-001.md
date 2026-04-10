# UC-AM-001: Create Asset via Data-First Flow

**Persona:** [Data Product Owner (DPO)](../personas/data-product-owner/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_commands_real_api.py::test_create_asset`

## Description

A Data Product Owner creates a new data asset by uploading a file (CSV,
Parquet, JSON), letting the platform infer schema and column statistics,
running an initial data-quality profile, and persisting the asset in the
catalog. This "data-first" flow prioritizes getting data into the
platform quickly, with metadata and contracts refined afterward.

## Preconditions

- The user is authenticated and holds the `DATA_PRODUCT_OWNER` or
  `EDITOR` role in the active tenant.
- The tenant's storage quota has not been exceeded.
- At least one supported file format is available for upload (CSV,
  Parquet, or JSON).

## Steps

1. DPO navigates to "Assets > Create New" or calls
   `POST /api/v1/assets` with `{ name, description, domain, tags[] }`.
2. The API creates an asset record in `DRAFT` status and returns the
   `asset_id`.
3. DPO uploads the data file via
   `POST /api/v1/assets/{asset_id}/upload` (multipart form-data).
4. The platform stores the file in the tenant's object-storage bucket,
   kicks off an asynchronous schema-inference job, and returns
   `202 Accepted` with a `job_id`.
5. The schema-inference job detects column names, data types, nullable
   flags, and basic statistics (row count, null percentage, unique
   count). Results are written to the asset's `schema` field.
6. DPO polls `GET /api/v1/jobs/{job_id}` or receives a webhook
   notification when the job completes.
7. The platform automatically triggers an initial DQ profile (see
   [UC-DQ-001](UC-DQ-001.md)). The DQ results (completeness, validity,
   uniqueness scores) are attached to the asset.
8. DPO reviews the inferred schema and DQ summary on the asset detail
   page, optionally editing column descriptions or adding tags.
9. DPO sets the asset status to `READY` via
   `PATCH /api/v1/assets/{asset_id}` with `{ status: "READY" }`.

## Expected Outcome

- A new asset exists in `READY` status with an inferred schema, column
  statistics, and an initial DQ score.
- The raw data file is stored in object storage and linked to the asset.
- An `AUDIT_ASSET_CREATED` event is recorded in the
  [audit log](../../concepts/audit-events.md).
- The asset is discoverable in the catalog via search and filters.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Unsupported file format | `415 Unsupported Media Type` |
| File exceeds size limit | `413 Payload Too Large` |
| Schema inference fails | Job status `FAILED` with diagnostic message |
| Storage quota exceeded | `507 Insufficient Storage` |

## Related

- Concepts: [Assets](../../concepts/assets.md), [Datasets](../../concepts/datasets.md), [DQ Runs](../../concepts/dq-runs.md), [Jobs](../../concepts/jobs.md)
- Journeys: [JOURNEY-DPO-001 -- Onboard New Asset via Data-First Flow](../journeys/JOURNEY-DPO-001.md)
- Personas: [Data Product Owner](../personas/data-product-owner/index.md)
