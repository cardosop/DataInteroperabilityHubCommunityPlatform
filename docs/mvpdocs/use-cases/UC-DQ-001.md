# UC-DQ-001: Run Data Quality Check

**Persona:** [Data Product Owner (DPO)](../personas/data-product-owner/index.md) / [Data Engineer (DE)](../personas/data-engineer/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_commands_real_api.py::test_dq_run`

## Description

A Data Product Owner or Data Engineer executes a data-quality (DQ)
profile against a registered asset, reviews the resulting scores and
column-level findings, and decides whether the asset meets the quality
bar for publication or continued use. DQ checks are also triggered
automatically during the data-first asset creation flow.

## Preconditions

- The asset exists and has at least one version with data uploaded (see
  [UC-AM-001](UC-AM-001.md)).
- The user holds `DATA_PRODUCT_OWNER`, `DATA_ENGINEER`, or `EDITOR`
  role.
- The DQ engine service is running and healthy.
- An optional DQ rule-set may be attached to the asset via a
  [data contract](../../concepts/contracts.md).

## Steps

1. DPO navigates to the asset's "Quality" tab and clicks "Run DQ
   Check", or calls `POST /api/v1/assets/{asset_id}/dq-runs` with an
   optional `{ rule_set_id }` to specify custom rules.
2. The API creates a `DQRun` record in `PENDING` status and enqueues a
   background job. Returns `202 Accepted` with `dq_run_id` and
   `job_id`.
3. The DQ engine reads the asset's latest data version and evaluates:
   - **Completeness:** Percentage of non-null values per column.
   - **Validity:** Values matching declared data-type and format
     constraints.
   - **Uniqueness:** Duplicate detection on key columns.
   - **Consistency:** Cross-column rule checks (if rule-set provided).
   - **Timeliness:** Freshness based on the latest update timestamp.
4. The engine writes results to the `DQRun` record, setting
   `status = COMPLETED` and populating `overall_score`, per-column
   scores, and individual finding records.
5. DPO polls `GET /api/v1/assets/{asset_id}/dq-runs/{dq_run_id}` or
   receives a webhook/feed notification on completion.
6. DPO reviews the DQ dashboard:
   - Overall score (0-100) with pass/fail indicator against the
     configured threshold.
   - Column-level heat map highlighting low-scoring columns.
   - Individual findings with severity, affected rows, and suggested
     remediation.
7. If the score meets the threshold, the asset remains in or progresses
   to `READY` status. If below threshold, the asset is flagged and the
   DPO is prompted to remediate or override.

## Expected Outcome

- A `DQRun` record exists with `status = COMPLETED`, an `overall_score`,
  and per-column detail.
- The asset's `latest_dq_score` field is updated.
- If attached to a data contract, contract compliance status is
  recalculated.
- An `AUDIT_DQ_RUN_COMPLETED` event is recorded in the
  [audit log](../../concepts/audit-events.md).
- Feed subscribers (stewards, asset watchers) are notified if the score
  drops below threshold.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Asset has no data uploaded | `422 Unprocessable Entity` |
| DQ engine unavailable | Job status `FAILED` with `ENGINE_UNAVAILABLE` |
| Rule-set not found | `404 Not Found` |
| Concurrent DQ run on same asset | `409 Conflict` |

## Related

- Concepts: [DQ Runs](../../concepts/dq-runs.md), [Assets](../../concepts/assets.md), [Contracts](../../concepts/contracts.md), [Jobs](../../concepts/jobs.md)
- Journeys: [JOURNEY-DPO-004 -- Monitor Asset Quality](../journeys/JOURNEY-DPO-004.md), [JOURNEY-DE-003 -- Configure Data Quality Checks](../journeys/JOURNEY-DE-003.md)
- Personas: [Data Product Owner](../personas/data-product-owner/index.md), [Data Engineer](../personas/data-engineer/index.md)
