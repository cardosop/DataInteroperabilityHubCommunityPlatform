# Transformation Pipelines

**Status:** DRAFT (285.5.3.J, 2026-05-17)
**Feature Flag:** `transformation_enabled`
**Gate:** DRAFT — core engine is synchronous placeholder. Gate until implemented.

## Current State

The transformation engine at `hub/apps/transformation/services.py` (3904L)
provides:

- `TransformationPipeline` model with step definitions
- `_execute_pipeline_sync()` (line 1274) — synchronous executor for small datasets
- `execute_pipeline()` (line 1360) — public entry point
- `_execute_pipeline_on_sample()` (line 2860) — sample-based preview execution

The engine works for simple CSV transformations but has known limitations:
1. **Synchronous only** — holds the request thread; no async Job execution
2. **CSV only** — no Parquet, JSON, or Avro support
3. **No Prefect integration** — cannot leverage existing Prefect worker infrastructure
4. **No lineage tracking** — transformations don't create lineage edges

## Follow-Up Plan (~4 weeks)

### Week 1–2: Async Job Execution
- Add `JobType.TRANSFORMATION` (already exists as `JobType.TRANSFORMATION`)
- Enqueue async job in `TransformationPipelineViewSet.create_execution()`
- Worker polls for PENDING jobs and executes via `_execute_pipeline_sync()`
- Job status: PENDING → RUNNING → COMPLETED/FAILED

### Week 3: Broader Format Support
- Add Parquet, JSON, Avro readers to `TransformationService`
- Schema inference per format
- Output format selection independent of input

### Week 4: Prefect Worker Integration
- Register transformation as a Prefect flow
- Reuse existing `hub-test-prefect-worker` container
- Support scheduled/triggered pipeline execution
- Add lineage edges from source → transformation → output dataset

## Related

- `hub/apps/transformation/services.py` — TransformationService (3904L)
- `hub/apps/transformation/models.py` — TransformationPipeline model
- `hub/apps/jobs/models.py` — `JobType.TRANSFORMATION`
- `hub/apps/tenants/feature_flag_registry.py` — `transformation_enabled` flag (DRAFT)

## Maintenance

- **Owner:** Data Plane Engineering
- **Last reviewed:** 2026-05-17
- **Next review:** 2026-08-17
