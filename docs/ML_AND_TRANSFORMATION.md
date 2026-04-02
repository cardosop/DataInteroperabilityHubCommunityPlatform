# ML & Transformation

> Machine learning platform (ML/AI PaaS) and data transformation pipeline documentation.

**Last Updated**: 2026-03-22
>
> **Source**: Phase 114 (ML/AI PaaS), Phase 115 (Data Transformation), Phase 117D (Root-Cause Fixes).

---

## Table of Contents

1. [ML/AI PaaS Overview](#1-mlai-paas-overview)
2. [Model Lifecycle](#2-model-lifecycle)
3. [Training Guide](#3-training-guide)
4. [Inference & Deployment](#4-inference--deployment)
5. [Marketplace Publishing](#5-marketplace-publishing)
6. [Best Practices](#6-best-practices)
7. [Transformation Pipeline Guide](#7-transformation-pipeline-guide)
8. [SQL Reference](#8-sql-reference)
9. [Plan Limits](#9-plan-limits)
10. [Classification Propagation](#10-classification-propagation)

---

## 1. ML/AI PaaS Overview

### Architecture

The ML platform integrates with Open Data Hub (ODH) for model training and inference:

```
┌──────────────┐     ┌─────────────────────┐     ┌────────────────────┐
│  Hub API      │────→│  ODH Model Registry  │────→│  Training Operator  │
│  (Django)     │     │  (port 8095)         │     │  (port 8096)        │
│               │────→│                      │     └────────────────────┘
│               │     └─────────────────────┘            │
│               │                                        ↓
│               │←────────────────────────────── Training Complete
│               │     ┌─────────────────────┐
│               │────→│  Inference Scheduler │
│               │     │  (port 8097)         │
└──────────────┘     └─────────────────────┘
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `ModelRegistryBridgeService` | `hub/apps/ml/services.py` | Core service: CRUD, deploy, lineage, marketplace |
| `TrainingJobOrchestrator` | `hub/apps/ml/training_orchestrator.py` | Training job submission, monitoring, completion |
| `ODHIntegrationBusinessRules` | `hub/apps/ml/business_rules.py` | Validation rules for model operations |
| `MLModel` | `hub/apps/ml/models.py` | Model metadata with `deployment_id` field |
| `ModelDatasetLink` | `hub/apps/ml/models.py` | Training/validation/test dataset links |

### ODH Integration

- **Model Registry**: Stores model metadata, versions, artifacts
- **Training Operator**: Submits and monitors training jobs
- **Inference Scheduler**: Manages model deployments and routes prediction requests
- **Graceful degradation**: All ODH interactions wrapped in try/except — platform continues with placeholders when ODH services are unavailable

---

## 2. Model Lifecycle

### Status Transitions

```
TRAINING → TRAINED → DEPLOYED → TRAINED (undeploy)
              ↑                    │
              └────────────────────┘ (undeploy/version switch)

TRAINING → FAILED
TRAINED → ARCHIVED
DEPLOYED → ARCHIVED
```

### Deployment Lifecycle (ML-1)

| Method | Action | Status Change |
|--------|--------|---------------|
| `deploy_model(model_id)` | Deploy trained model | TRAINED → DEPLOYED |
| `undeploy_model(model_id)` | Undeploy model | DEPLOYED → TRAINED |
| `deploy_version(odh_id, version)` | Atomic version switch | Undeploy current + deploy target |
| `rollback_deployment(odh_id, version)` | Rollback to version | Delegates to `deploy_version()` |

- **`deployment_id`**: Stored on `MLModel` field (`CharField(max_length=255, null=True)`)
- **Concurrency safety**: All deploy/undeploy use `select_for_update()` row locking
- **Audit**: `MODEL_DEPLOYED` audit event created on deployment

### Semantic Layer Auto-Update (ML-4)

When training completes, `_update_semantic_layer_task()` ingests RDF triples:

```turtle
@prefix odh: <http://odh.io/ontology/> .
odh:model/{odh_model_id} a odh:MLModel ;
  odh:modelType "CLASSIFICATION" ;
  odh:odhModelId "model-abc123" ;
  odh:odhModelVersion "1.0" ;
  odh:created "2026-03-22T00:00:00Z"^^xsd:dateTime ;
  odh:trainingDataset odh:dataset/{dataset_id} .
```

Ingested via `SemanticServiceClient.ingest_rdf()` in Turtle format.

### Lineage Graph (ML-10)

```
DATASET ──TRAINS_TRAINING──→ ML_MODEL ──PRODUCES──→ ASSET
DATASET ──TRAINS_VALIDATION──→ ML_MODEL
DATASET ──TRAINS_TEST──→ ML_MODEL
```

`add_ml_model_lineage()` creates edge records from `ModelDatasetLink` relationships. Called automatically from `link_model_to_dataset()`.

### ODH Deployment Verification (ML-5)

`_validate_model_deployment_task()` checks deployment readiness:

1. Read `model.deployment_id` (populated by `deploy_model()`)
2. Validate via `ODHIntegrationBusinessRules.validate_model_deployment()`
3. Fallback: query ODH Inference Scheduler if `deployment_id` not set
4. Store deployment info in workflow `state_data`

---

## 3. Training Guide

### Submitting a Training Job

```python
service = ModelRegistryBridgeService(tenant_id=str(tenant.id), user_id=str(user.id))

# Link dataset to model
service.link_model_to_dataset(
    model_id=str(model.id),
    dataset_id=str(dataset.id),
    role="TRAINING",  # TRAINING, VALIDATION, or TEST
)

# Submit training job
service.train_model_with_workflow(
    model_id=str(model.id),
    dataset_id=str(dataset.id),
    training_config={"timeout": 7200, "epochs": 100},
    hyperparameters={"learning_rate": 0.01},
)
```

### Configurable Timeout (ML-6)

Training timeout is resolved in priority order:

1. **`training_config.timeout`**: Explicit per-job timeout
2. **`plan.limits_json.ml_training_timeout`**: Tenant plan limit
3. **Default**: 3600 seconds (1 hour)

```python
# TrainingJobOrchestrator._resolve_timeout()
timeout = training_config.get("timeout")        # Priority 1
    or plan.limits_json.get("ml_training_timeout")  # Priority 2
    or 3600                                          # Priority 3
```

### Cross-Tenant Training Guard (ML-7)

- Models and datasets must belong to the same tenant
- Validated in `ODHIntegrationBusinessRules.validate_model_dataset_linking()`
- Cross-tenant training requires explicit marketplace entitlement (M3)
- Violation raises `ValidationError("MODEL_DATASET_LINKING_INVALID")`

### Usage Metering (ML-2)

Inference requests are metered via `BillingService.record_usage()`:

| Metric Key | Quantity | Description |
|------------|----------|-------------|
| `ml_inference_requests` | 1 per request | Count of inference calls |
| `ml_inference_compute_ms` | response_time_ms | Compute time per request |

Metering happens in `_update_usage_tracking_task()` after inference completes. Failures are non-fatal (logged but don't block response).

---

## 4. Inference & Deployment

### Deploying a Model

```python
service = ModelRegistryBridgeService(tenant_id=str(tenant.id), user_id=str(user.id))

# Deploy (TRAINED → DEPLOYED)
model = service.deploy_model(str(model.id))
print(f"Deployed: {model.deployment_id}")

# Run inference
result = service.run_inference_with_workflow(
    model_id=str(model.id),
    input_data={"features": [1.0, 2.0, 3.0]},
)
```

### Version Management (ML-8)

```python
# Deploy version 2.0 (atomically undeploys 1.0)
model = service.deploy_version("odh-model-abc", "2.0")

# Rollback to version 1.0
model = service.rollback_deployment("odh-model-abc", "1.0")
```

`deploy_version()` is `@transaction.atomic` with `select_for_update()`:
1. Find all currently deployed versions of the model
2. Undeploy each (status→TRAINED, clear deployment_id)
3. Deploy target version (status→DEPLOYED, set deployment_id)

---

## 5. Marketplace Publishing

### Publishing a Model (Integration-2)

```python
result = service.publish_model_to_marketplace(
    model_id=str(model.id),
    pricing_model="FREE",  # FREE, FREE_AUTO_APPROVE, REQUEST_APPROVAL
)
# Returns: {"listing_id": "...", "model_id": "...", "asset_id": "..."}
```

Requirements:
- Model must be linked to an asset (`model.asset_id` is not None)
- Asset must be in ACTIVE status (enforced by Listing model's `clean()`)
- Listing metadata includes `product_category=ml_model`, model_type, version, status

---

## 6. Best Practices

### Dataset Preparation

- Always link training, validation, AND test datasets before submitting training
- Use `role="TRAINING"` for primary dataset (sets `model.training_dataset_id`)
- Validate data quality (run DQ checks) before linking to model

### Cross-Tenant Requirements

- Same-tenant datasets: link directly
- Cross-tenant datasets: requires marketplace entitlement (M3)
- Classification propagation (G5): PII/PHI/PCI classifications auto-propagate from dataset to model's asset

### Deployment Checklist

1. Verify model status is TRAINED
2. Review classification propagation results (check asset classifications)
3. Deploy model (`deploy_model()`)
4. Verify deployment via inference test
5. Monitor inference metrics
6. Consider publishing to marketplace

---

## 7. Transformation Pipeline Guide

### Overview

Transformation pipelines process data through a node-based DAG:

```
Source Data → [Filter] → [Map] → [Aggregate] → [Join] → Output Dataset
```

### Pipeline Modes

| Mode | Engine | Use Case |
|------|--------|----------|
| SQL | DuckDB | Complex queries, aggregations, joins |
| Visual | Polars | Drag-and-drop node-based transformations |

### Pipeline Lifecycle

1. **Create**: Define pipeline with name, description, nodes
2. **Validate**: Check DAG connectivity, node configs, input/output compatibility
3. **Preview**: Execute on sample data (first 100 rows)
4. **Execute**: Submit full pipeline run
5. **Monitor**: Track progress, view errors, cancel if needed

### Event Triggers

Pipelines can be triggered by:
- **Manual**: `POST /transformation/pipelines/{id}/runs/`
- **Schedule**: Cron-based via scheduled export integration
- **Event**: Dataset version created, file upload completed

---

## 8. SQL Reference

### DuckDB SQL Subset

Transformation pipelines support a safe subset of DuckDB SQL:

**Allowed Statements:**
- `SELECT`, `WITH` (CTEs), `UNION`, `INTERSECT`, `EXCEPT`
- All standard functions (aggregates, string, date, math)
- Window functions (`ROW_NUMBER`, `RANK`, `LAG`, `LEAD`)
- `COPY ... TO` for export

**Blocked Statements:**
- `CREATE`, `DROP`, `ALTER`, `INSERT`, `UPDATE`, `DELETE`
- `ATTACH`, `DETACH` (database manipulation)
- System functions and pragmas

**S3 Source Syntax:**
```sql
SELECT * FROM read_parquet('s3://bucket/path/file.parquet')
SELECT * FROM read_csv('s3://bucket/path/file.csv', header=true)
```

---

## 9. Plan Limits

### ML & Transformation Limits (B4)

| Limit Key | Free | Pro | Enterprise |
|-----------|------|-----|------------|
| `max_ml_models` | 2 | 20 | Unlimited |
| `max_ml_training_jobs_per_month` | 5 | 50 | Unlimited |
| `max_ml_inference_requests_per_month` | 1,000 | 50,000 | Unlimited |
| `max_ml_deployed_models` | 1 | 5 | 20 |
| `max_transformation_pipelines` | 3 | 30 | Unlimited |
| `max_odps_documents` | 5 | 50 | Unlimited |
| `ml_training_timeout` | 3600s | 7200s | 14400s |

Limits enforced via `limit_registry.get_resource_count()` in business rules validation.

---

## 10. Classification Propagation

### G5: Input Datasets → Model → Asset

When a model is linked to a dataset containing classified data:

1. `link_model_to_dataset()` triggers `propagate_classification()`
2. Finds highest-priority classification on source dataset
3. Creates/updates classification on model's asset with provenance

**Priority Order:**
```
PUBLIC (1) < INTERNAL (2) < CONFIDENTIAL (3) < RESTRICTED (4) < PII (5) < PHI/PCI (6)
```

**Example:** Dataset has PII classification → model's asset automatically gets PII classification with note: `"Propagated from DATASET:{dataset_id}"`

This ensures data governance requirements flow through the ML pipeline — a model trained on PII data is itself classified as handling PII.
