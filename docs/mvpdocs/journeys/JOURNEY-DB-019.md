# JOURNEY-DB-019: Register a Model in Unity Catalog

**Persona:** Data Scientist (DS)
**Use Cases:** UC-DB-019

## Overview

A data scientist registers ML models and model versions in Unity Catalog from the Hub. The CORE control plane manages the Databricks-side assets — registered models + versions via the MLflow REST surface on the PINNED client (the 2.0 `mlflow.*` pins, design D2 — the UC REST has no registered-model-create endpoint), aliases via the UC REST, and feature tables via the `feature_store` tag convention — without importing any paid `ml`/`ai` app code (GATE-29).

## Journey Steps

1. **Register a model** — The Hub ensures the registered model in a UC catalog/schema through the MLflow REST surface on the pinned client (`mlflow.registered_models.get/create` — the GET's 404 creates, never a blind create; grants/tagging for models use the `FUNCTION` securable type).
2. **Log a version** — The Hub logs the version through the MLflow REST surface (`mlflow.model_versions.create` on the pinned client — never a second HTTP stack; the `mlflow` python package stays a dev-only protocol oracle at most).
3. **Set an alias** — The user assigns/removes model aliases (`PUT /api/2.1/unity-catalog/models/{full_name}/aliases/{alias}`) for stage promotion.
4. **Tag feature tables** — Feature-store tables are UC tables carrying the `feature_store` tag convention.
5. **Serve (optional)** — Flag-gated Vector Search and serving endpoint management round out the ML-assets surface.

## Success Criteria

- Zero imports from paid `ml`/`ai` apps — `scripts/check_core_boundary.py` stays green.
- Model registration, version logging, and alias CRUD each emit audit events.
- A flag-off tenant answers 403 `DATABRICKS_ML_ASSETS_DISABLED`; an unknown model answers 404 `DATABRICKS_UC_OBJECT_NOT_FOUND` (the UC-DB-019 error table, implemented in 12.6).
- Alias and tag conventions round-trip through the UC APIs.
- All ML-asset endpoints are flag-gated (default-off).

## Related

- Concepts: [Feature Availability](../concepts/feature-availability.md), [Audit Events](../concepts/audit-events.md)
- How-To: [Data Scientist How-To Guides](../personas/data-scientist/how-to/)
- Journeys: [JOURNEY-DB-005](JOURNEY-DB-005.md) (Browse the Unity Catalog)
