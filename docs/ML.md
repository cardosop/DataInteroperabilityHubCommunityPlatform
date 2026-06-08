# ML Platform

**Status:** CANARY (285.5.3.I, 2026-05-17)
**Feature Flag:** `ml_enabled`
**Approach:** Two-Phase

## Phase 1 — Model Registry (Current)

### MLModelVersion Model

```
MLModelVersion:
  id: UUID (PK)
  model: FK → MLModel
  version_number: Int (auto-increment per model)
  framework: Str (sklearn, pytorch, tensorflow, xgboost, custom)
  artifact_uri: Str (S3 URI)
  metrics_json: JSONField (accuracy, precision, recall, f1, etc.)
  tenant: FK → Tenant (RLS)
  created_at: DateTime
```

### Catalog Integration

- ML models appear in `UnifiedSearchView` with type `ML_MODEL`
- Models linked to training datasets via lineage edges
- Search filters: framework, metric threshold, creation date
- `MLModel` detail page shows version history, metrics, lineage

### RLS Policy

All ML models require tenant-scoped RLS. The `MLModel` and `MLModelVersion`
tables ship with paired RLS policy migrations per the Tenant Isolation contract.

### CLI + SDK

- `datahub ml models list|get|create` — model registry commands
- `client.ml` — `TrainingAPI`, `InferenceAPI`, `ModelRegistryAPI`

## Phase 2 — Inference Serving (Future)

Gated on tenant demand. Planned capabilities:
- Model deployment to inference endpoints
- A/B testing between model versions
- Auto-scaling based on request volume
- Inference metrics dashboards (latency, throughput, error rate)

## Phase 2 — Inference Serving (On Hold)

**Gate:** 3+ PRO tenants requesting inference serving. Estimated: 12+ weeks.

Planned capabilities:
- Async inference queue with priority scheduling
- GPU scheduling (NVIDIA GPU Operator integration)
- A/B testing between model versions
- Usage tracking per model version
- Stripe billing integration (per-inference pricing tier)

## Phase 2 Trigger Conditions

Phase 2 activates when:
- ≥3 PRO tenants have requested inference serving
- ≥2 enterprise prospects request inference serving during sales
- Phase 1 Model Registry is ≥95 audit score

## Related

- `hub/apps/ml/models.py` — MLModel, MLModelVersion
- `hub/apps/ml/views.py` — MLModelViewSet
- `hub/apps/tenants/feature_flag_registry.py` — `ml_enabled` flag (CANARY)
- `docs/ga-readiness-audit-2026-05.md`

## Maintenance

- **Owner:** ML Engineering
- **Last reviewed:** 2026-05-17
- **Next review:** 2026-08-17
