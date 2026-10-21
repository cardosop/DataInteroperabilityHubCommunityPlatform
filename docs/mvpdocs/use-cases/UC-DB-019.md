# UC-DB-019: Register UC Model

**Persona:** Data Scientist (DS)
**MVP Tier:** :white_check_mark:
**Phase P12 Test:** `hub/apps/databricks_admin/tests/test_ml_assets_journeys.py::TestJOURNEYDB019RegisterUCModel::test_mlflow_version_log`

## Description

Register ML models and versions in Unity Catalog from the Hub CORE app: registered models + versions via the MLflow REST surface on the PINNED client (the 2.0 `mlflow.*` pins, design D2 — the UC REST has no registered-model-create endpoint), aliases via the UC REST for stage promotion, and feature tables via the `feature_store` tag convention — with zero imports from the paid `ml`/`ai` apps.

## Preconditions

- `databricks_ml_assets_enabled=True` for the tenant.
- A registered workspace with a target catalog/schema.

## Steps

1. User registers a model through the MLflow REST surface on the pinned client (`mlflow.registered_models.get/create` — the GET's 404 creates; grants/tagging use the `FUNCTION` securable type).
2. The Hub logs a version through the MLflow REST surface (`mlflow.model_versions.create` on the pinned client — never a second HTTP stack).
3. User sets/removes aliases (`PUT/DELETE /api/2.1/unity-catalog/models/{full_name}/aliases/{alias}`).
4. Feature tables are tagged with the `feature_store` convention; serving/vector endpoints are flag-gated.

## Expected Outcome

- `scripts/check_core_boundary.py` stays green (zero paid imports).
- Each operation emits its own audit event.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Feature flag off | `403` |
| Model not found | `404` with `DATABRICKS_UC_OBJECT_NOT_FOUND` |

## Related

- Concepts: [Feature Availability](../concepts/feature-availability.md), [Audit Events](../concepts/audit-events.md)
- Journeys: [JOURNEY-DB-019 -- Register a Model in Unity Catalog](../journeys/JOURNEY-DB-019.md)
- Personas: Data Scientist (DS)
