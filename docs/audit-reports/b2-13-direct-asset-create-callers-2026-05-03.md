# B2-13 audit — direct `Asset.objects.create()` / `Asset(...)` callers

**Audit task**: 250.0.10
**Audit date**: 2026-05-03
**Auditor**: Phase 250.0 Asset-Creation-Hardening pre-flight
**Status**: ✅ **CATALOGUED — 9 production call sites identified; refactor plan below**

## Original gap statement

B2-13: "production code may bypass `AssetService` and call `Asset.objects.create()` directly, leaving the gates (compliance / DQ / fail-closed) un-enforced. Each bypass is a hole in the workflow re-sequence (Phase 250.1.A) — the re-sequence only matters if every Asset-creation path runs through the gates."

## Methodology

Repository-wide grep:
```
grep -rnE 'Asset\.objects\.create|^Asset\(' hub/ \
  | grep -v migrations \
  | grep -v __pycache__ \
  | grep -v '/tests/'
```

## Findings (9 production call sites)

| # | File | Line | Context | Refactor verdict |
|---|---|---|---|---|
| 1 | [hub/apps/scheduled_ingestion/ingestion.py](../../hub/apps/scheduled_ingestion/ingestion.py) | 441 | Scheduled-ingestion creates an Asset on a recurring schedule (cron-driven). Already-trusted source (configured by tenant); BUT must run through compliance + DQ gates per Phase 250.1.A spec. | **REFACTOR via `AssetService.create_via_workflow(...)`** in Phase 250.1.G |
| 2 | [hub/apps/orchestration/workflows/contract_creation.py](../../hub/apps/orchestration/workflows/contract_creation.py) | 633 | Contract-first workflow creates a placeholder Asset. Pre-Phase-250 ordering: Asset persisted FIRST, then contract attached. Phase 250.1.A flips this. | **REFACTOR — gates run BEFORE asset persists**; merge into the new fail-closed sequence |
| 3 | [hub/apps/orchestration/workflows/product_creation.py](../../hub/apps/orchestration/workflows/product_creation.py) | 1748 | Mesh data-product creation flow. Mesh products MAY have multiple Assets; each individually-created Asset must run through gates. | **REFACTOR — call `AssetService.create_via_workflow(...)` per child asset** |
| 4 | [hub/apps/orchestration/workflows/asset_creation.py](../../hub/apps/orchestration/workflows/asset_creation.py) | 639 | The canonical asset-creation workflow itself. Currently creates Asset → then runs gates. Phase 250.1.A inverts: gates → then create. | **PRIMARY refactor target — Phase 250.1.A fix-locus** |
| 5 | [hub/apps/orchestration/workflows/transformation_pipeline.py](../../hub/apps/orchestration/workflows/transformation_pipeline.py) | 230 | Transformation pipeline creates a result asset (output of a transform). Output is derived from already-vetted inputs but may produce new PII. | **REFACTOR — must run compliance scan on derived data**; DQ optional based on transformation type |
| 6 | [hub/apps/assets/views_optimized.py](../../hub/apps/assets/views_optimized.py) | 168 | Direct API path that bypasses the orchestration workflow. **Highest-risk bypass** — view that creates an Asset row WITHOUT going through gates. | **REFACTOR — replace with delegation to `AssetService.create_via_workflow(...)`** |
| 7 | [hub/apps/integrations/services/discovery_service.py](../../hub/apps/integrations/services/discovery_service.py) | 223 | Marketplace discovery / federated import path. Federated assets per D250.3 require compliance gate but skip DQ for METADATA_ONLY. | **REFACTOR — federated-import-specific workflow path that runs compliance only** |
| 8 | [hub/apps/integrations/_services_legacy.py](../../hub/apps/integrations/_services_legacy.py) | 2712 | Legacy services file flagged by name as obsolete; if still in use, must conform to D250.3. | **AUDIT FIRST — confirm if production code paths reach this; if dead code, delete; if live, REFACTOR via federated workflow** |
| 9 | [hub/apps/orchestration/workflows/scheduled_ingestion.py](../../hub/apps/orchestration/workflows/scheduled_ingestion.py) | 999 | Mirror of #1 inside the orchestration package; possible duplicate of `scheduled_ingestion/ingestion.py:441`. | **AUDIT — confirm duplicate; deduplicate or align** |

## Refactor plan (paired with 250.1.A re-sequence)

The re-sequence in Phase 250.1.A introduces a new service entry point:

```python
# hub/apps/assets/services.py (new or extended)
class AssetService:
    @classmethod
    def create_via_workflow(
        cls,
        *,
        tenant,
        actor,
        file_id: UUID | None = None,
        contract_payload: dict,
        source_type: str = "HUB_NATIVE",
        data_strategy: str = "DOWNLOAD_ALL",
        idempotency_key: str | None = None,
        skip_compliance: bool = False,
        skip_dq: bool = False,
        workflow_version: int | None = None,
    ) -> WorkflowRun:
        """Single canonical entry point for Asset creation.
        
        Returns a WorkflowRun (NOT an Asset) — Asset row is materialised
        ONLY after compliance + DQ gates pass per D250.2 fail-closed parity.
        Callers poll the run via `WorkflowService.get_run(run.id)` until
        terminal state.
        """
```

Each of the 9 call sites becomes a `AssetService.create_via_workflow(...)` invocation with the appropriate `skip_compliance` / `skip_dq` / `source_type` / `data_strategy` parameters:

| # | New caller pattern |
|---|---|
| 1 | `create_via_workflow(source_type="HUB_NATIVE", skip_compliance=False, skip_dq=False)` |
| 2 | `create_via_workflow(source_type="HUB_NATIVE", contract_payload=...)` |
| 3 | `create_via_workflow(...)` per child asset; mesh-aware extension hook |
| 4 | This IS the workflow; refactor the workflow body to invert (gates → persist) |
| 5 | `create_via_workflow(skip_dq=True)` — transformation outputs run compliance only |
| 6 | DELETE the optimised-bypass view; expose `create_via_workflow` through the standard view |
| 7 | `create_via_workflow(source_type="FEDERATED", data_strategy="METADATA_ONLY", skip_dq=True)` |
| 8 | If legacy: delete; if live: align with #7 |
| 9 | Deduplicate with #1 |

## Migration strategy (rolling-deploy-safe per D250.5)

1. **Land `AssetService.create_via_workflow()` first** (Phase 250.1.A new code, behind `Tenant.compliance_fail_closed_enabled` flag default-FALSE on existing tenants per D250.12).
2. **Land all 9 caller refactors in separate PRs**, each with a feature-flag check:
   ```python
   if tenant.compliance_fail_closed_enabled:
       return AssetService.create_via_workflow(...)
   else:
       return Asset.objects.create(...)  # DEPRECATED — 30-day notice period
   ```
3. **30-day soak with feature flag default-FALSE on existing tenants**.
4. **Flip flag default to TRUE on existing tenants** after 14d production-stable telemetry.
5. **Delete the legacy `Asset.objects.create()` paths** in a follow-up cleanup PR (post-Phase-250 deprecation phase 2).
6. **Add a CI lint** (`scripts/check_asset_create_bypass.py`) that flags any new `Asset.objects.create()` outside `hub/apps/assets/services.py` and `hub/apps/assets/migrations/`.

## Coverage matrix

The Phase 250.1.A test plan MUST exercise each of the 9 call-site categories:

| Test name | Covers |
|---|---|
| `test_workflow_creates_asset_after_gates_pass` | Sites 4, 6 |
| `test_workflow_rejects_when_compliance_fails_closed` | Sites 1, 2, 4, 6, 9 |
| `test_workflow_rejects_when_dq_fails_closed` | Sites 1, 2, 4, 6, 9 |
| `test_federated_import_runs_compliance_skips_dq` | Sites 7, 8 |
| `test_transformation_pipeline_runs_compliance_skips_dq` | Site 5 |
| `test_mesh_data_product_creates_each_child_via_service` | Site 3 |
| `test_legacy_create_bypass_blocked_by_lint` | All sites (CI gate) |

## Closeout

Phase 250 tasks.md sub-task **250.1.G** ("Webhook + internal-API consumer migration (MEDIUM, closes B2-6 / B2-7)") owns the lint guard + caller-migration; this audit report is the source-of-truth for the 9 sites that need refactoring. Tasks.md should reference this report inline.
